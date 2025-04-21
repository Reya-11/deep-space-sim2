import grpc
from concurrent import futures
import sqlite3
import time
import threading
import socket
import json
import math
import random

import space_telemetry_pb2 as telemetry_pb2
import space_telemetry_pb2_grpc as telemetry_pb2_grpc

DB_FILE = "telemetry_data.db"
visualization_clients = []
comm_stats = {
    "packets_sent": 0,
    "packets_received": 0,
    "packets_lost": 0,
    "packet_loss_rate": 0.0,
    "signal_delay": 0.0,
    "data_volume_kb": 0.0
}

class TelemetryStats:
    def __init__(self):
        self.packets_received = 0
        self.packets_corrupted = 0
        self.anomalies_detected = 0
        self.data_volume = 0  # bytes

    def update(self, size, corrupted=False, has_anomalies=False):
        self.packets_received += 1
        self.data_volume += size
        if corrupted:
            self.packets_corrupted += 1
        if has_anomalies:
            self.anomalies_detected += 1

    def get_stats(self):
        return {
            "packets_received": self.packets_received,
            "packets_corrupted": self.packets_corrupted,
            "anomalies_detected": self.anomalies_detected,
            "data_volume_kb": self.data_volume / 1024,
            "packet_loss_rate": self.packets_corrupted / max(self.packets_received, 1)
        }

class ReceiverService(telemetry_pb2_grpc.TelemetryServiceServicer):
    def __init__(self):
        self.stats = TelemetryStats()
        self.recent_packets = []

    def SendTelemetry(self, request, context):
        print(f"\n[RECEIVER] 🛰️ {request.spacecraft_id} @ {request.timestamp:.2f}")

        # Validate checksum if possible
        local_checksum = self._calculate_checksum(request)
        is_corrupted = random.random() < 0.05
        has_anomalies = request.anomaly_detected if hasattr(request, 'anomaly_detected') else False

        self.stats.update(1024, corrupted=is_corrupted, has_anomalies=has_anomalies)

        # Show data
        print(f"  → Pos: ({request.position_x:.1f}, {request.position_y:.1f}, {request.position_z:.1f})")
        print(f"  → Temp: {request.temperature:.1f}°C | Anomalies: {request.anomaly_count} | Severity: {request.anomaly_severity}")
        if hasattr(request, 'signal_quality'):
            print(f"  → Signal Quality: {request.signal_quality:.1f}%")

        # Log SOS if present
        if getattr(request, 'sos_required', False):
            print(f"  🚨 SOS Received: {request.sos_reason}")

        # Save to DB
        save_to_db(request)

        # Stream to UI
        self._stream_to_ui(request)

        # Update comm stats
        self.process_telemetry_data(request)

        # Periodic stats print
        if self.stats.packets_received % 10 == 0:
            s = self.stats.get_stats()
            print(f"\n[RECEIVER STATS] 📊 {s['packets_received']} packets | {s['data_volume_kb']:.1f} KB | Loss: {s['packet_loss_rate']:.2%}")

        # Return response with checksum for edge verification
        return telemetry_pb2.TelemetryData(
            spacecraft_id=request.spacecraft_id,
            timestamp=time.time(),
            position_x=request.position_x,
            position_y=request.position_y,
            position_z=request.position_z,
            velocity_x=request.velocity_x,
            velocity_y=request.velocity_y,
            velocity_z=request.velocity_z,
            temperature=local_checksum  # reuse for checksum return
        )

    def _calculate_checksum(self, telemetry):
        vals = [
            telemetry.position_x, telemetry.position_y, telemetry.position_z,
            telemetry.velocity_x, telemetry.velocity_y, telemetry.velocity_z,
            telemetry.temperature
        ]
        return sum(math.isnan(v) and 0 or v for v in vals)

    def _stream_to_ui(self, request):
        global visualization_clients, comm_stats
        
        # Update comm stats
        comm_stats["packets_received"] += 1
        
        # Calculate signal delay if timestamp is available
        if hasattr(request, 'timestamp'):
            packet_time = float(request.timestamp)
            comm_stats["signal_delay"] = time.time() - packet_time
            
        # Calculate loss using sequence numbers if available
        if hasattr(request, 'sequence_num'):
            expected_sequence = getattr(self, 'last_sequence_num', 0) + 1
            if request.sequence_num > expected_sequence:
                # Packets were lost
                comm_stats["packets_lost"] += (request.sequence_num - expected_sequence)
            self.last_sequence_num = request.sequence_num
            
        # Calculate loss rate
        total_packets = comm_stats["packets_received"] + comm_stats["packets_lost"] 
        if total_packets > 0:
            comm_stats["packet_loss_rate"] = (comm_stats["packets_lost"] / total_packets) * 100
        
        # Debug the data structure being sent
        print(f"[RECEIVER] Preparing data stream with anomaly count: {request.anomaly_count}")
        
        # Create proper JSON structure
        packet_data = {
            "spacecraft_id": request.spacecraft_id,
            "timestamp": request.timestamp,
            "position_x": request.position_x,
            "position_y": request.position_y, 
            "position_z": request.position_z,
            "velocity_x": request.velocity_x,
            "velocity_y": request.velocity_y,
            "velocity_z": request.velocity_z,
            "temperature": request.temperature,
            "anomaly_count": request.anomaly_count,
            "anomaly_severity": request.anomaly_severity,
            "anomaly_descriptions": request.anomaly_descriptions,
            "signal_quality": getattr(request, 'signal_quality', 100.0),
            "sequence_num": getattr(request, 'sequence_num', 0),
            "anomaly_detected": request.anomaly_count > 0,
            "comm_stats": comm_stats
        }
        
        # Convert to proper JSON string
        data = json.dumps(packet_data) + '\n'  # Add newline character
        
        # Send to clients without any extra headers or prefixes
        for client in visualization_clients[:]:  # Create a copy to safely modify
            try:
                client.send(data.encode('utf-8'))
                print("Sent data to visualization client", data.encode('utf-8'))
            except Exception as e:
                print(f"[RECEIVER] Error sending data to visualization client: {e}")
                try:
                    client.close()
                except:
                    pass
                visualization_clients.remove(client)

    def process_telemetry_data(self, request):
        # Update comm stats
        global comm_stats
        
        # Track received packets
        comm_stats["packets_received"] += 1
        
        # Calculate signal delay if timestamp is available
        if hasattr(request, 'timestamp'):
            packet_time = float(request.timestamp)
            comm_stats["signal_delay"] = time.time() - packet_time
            
        # Calculate loss using sequence numbers if available
        if hasattr(request, 'sequence_num'):
            expected_sequence = getattr(self, 'last_sequence_num', 0) + 1
            if request.sequence_num > expected_sequence:
                # Packets were lost
                comm_stats["packets_lost"] += (request.sequence_num - expected_sequence)
            self.last_sequence_num = request.sequence_num
            
        # Calculate loss rate
        total_packets = comm_stats["packets_received"] + comm_stats["packets_lost"]
        if total_packets > 0:
            comm_stats["packet_loss_rate"] = (comm_stats["packets_lost"] / total_packets) * 100
        
        # Estimate data volume (approximate)
        comm_stats["data_volume_kb"] += 1.2  # Average packet size in KB
        
        # Add comm_stats to the telemetry data returned to clients
        telemetry_dict = {
            "spacecraft_id": request.spacecraft_id,
            "timestamp": request.timestamp,
            "position_x": request.position_x,
            "position_y": request.position_y,
            "position_z": request.position_z,
            "velocity_x": request.velocity_x,
            "velocity_y": request.velocity_y,
            "velocity_z": request.velocity_z,
            "temperature": request.temperature,
            "anomaly_count": request.anomaly_count,
            "anomaly_severity": request.anomaly_severity,
            "anomaly_descriptions": request.anomaly_descriptions,
            "signal_quality": getattr(request, 'signal_quality', 100.0),
            "anomaly_detected": request.anomaly_count > 0,
            "comm_stats": comm_stats
        }
        
        return telemetry_dict


# ========== DB & UTILITIES ==========

def save_to_db(data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spacecraft_id TEXT,
            timestamp REAL,
            position_x REAL,
            position_y REAL,
            position_z REAL,
            velocity_x REAL,
            velocity_y REAL,
            velocity_z REAL,
            temperature REAL
        )
    """)
    c.execute("""
        INSERT INTO telemetry (spacecraft_id, timestamp, position_x, position_y, position_z,
                               velocity_x, velocity_y, velocity_z, temperature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.spacecraft_id, data.timestamp,
        data.position_x, data.position_y, data.position_z,
        data.velocity_x, data.velocity_y, data.velocity_z,
        data.temperature
    ))
    conn.commit()
    conn.close()

def visualization_server():
    global visualization_clients
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 50051))
    s.listen(5)
    print("[RECEIVER] 📡 Visualization server started on port 50051")

    while True:
        client, addr = s.accept()
        print(f"[RECEIVER] UI connected: {addr}")
        visualization_clients.append(client)
        try:
            client.send(b'{"type":"ping"}\n')
        except:
            pass


# ========== MAIN SERVER ==========

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(
        ReceiverService(), server)
    server.add_insecure_port("[::]:50053")
    server.add_insecure_port("[::]:50054")

    threading.Thread(target=visualization_server, daemon=True).start()

    server.start()
    print("Receiver running on ports 50053 (primary) & 50054 (backup)")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)
        print("Receiver server stopped.")


if __name__ == "__main__":
    serve()
