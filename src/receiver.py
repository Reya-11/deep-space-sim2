import grpc
import time
import sqlite3
import socket
import json
import threading
from concurrent import futures
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

class TelemetryReceiver(space_telemetry_pb2_grpc.TelemetryServiceServicer):
    def __init__(self):
        self.setup_database()
        # Start visualization socket server
        self.visualization_clients = []
        threading.Thread(target=self.start_visualization_server, daemon=True).start()
        
    def setup_database(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect('telemetry_data.db')
        c = conn.cursor()
        
        c.execute('''
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
            temperature REAL,
            radiation_level REAL,
            energy_level REAL,
            mode TEXT,
            alert_level TEXT,
            receive_time REAL
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def start_visualization_server(self):
        """Start a socket server for visualization clients"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('localhost', 50051))
        server_socket.listen(5)
        print("[RECEIVER] Visualization server started on port 50051")
        
        # Accept visualization clients
        while True:
            try:
                client_socket, addr = server_socket.accept()
                print(f"[RECEIVER] Visualization client connected: {addr}")
                self.visualization_clients.append(client_socket)
            except Exception as e:
                print(f"[RECEIVER] Error accepting visualization client: {e}")
                time.sleep(1)
    
    def broadcast_to_visualization(self, data):
        """Send data to all connected visualization clients"""
        if not self.visualization_clients:
            return
            
        # Convert telemetry to JSON
        json_data = json.dumps(data) + "\n"  # Add newline as message delimiter
        
        # Send to all clients
        disconnected = []
        for client in self.visualization_clients:
            try:
                client.sendall(json_data.encode('utf-8'))
            except:
                disconnected.append(client)
                
        # Remove disconnected clients
        for client in disconnected:
            try:
                client.close()
            except:
                pass
            self.visualization_clients.remove(client)
            print("[RECEIVER] Visualization client disconnected")
        
    def SendTelemetry(self, request, context):
        """Handle incoming telemetry data"""
        print(f"[RECEIVER] Got telemetry from {request.spacecraft_id} @ {request.timestamp}")
        
        # Store in database
        receive_time = time.time()
        conn = sqlite3.connect('telemetry_data.db')
        c = conn.cursor()
        
        # Handle the case where new fields may not be present in older messages
        radiation_level = getattr(request, 'radiation_level', 0)
        energy_level = getattr(request, 'energy_level', 0)
        mode = getattr(request, 'mode', "UNKNOWN")
        alert_level = getattr(request, 'alert_level', "UNKNOWN")
        
        c.execute('''
        INSERT INTO telemetry 
        (spacecraft_id, timestamp, position_x, position_y, position_z, 
         velocity_x, velocity_y, velocity_z, temperature, radiation_level, 
         energy_level, mode, alert_level, receive_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            request.spacecraft_id, 
            request.timestamp, 
            request.position_x, 
            request.position_y, 
            request.position_z,
            request.velocity_x, 
            request.velocity_y, 
            request.velocity_z, 
            request.temperature,
            radiation_level,
            energy_level,
            mode,
            alert_level,
            receive_time
        ))
        
        conn.commit()
        conn.close()
        
        # Log alerts if present
        if hasattr(request, 'alert_level') and request.alert_level != "NOMINAL":
            print(f"[RECEIVER] ALERT: {request.spacecraft_id} has {request.alert_level} status")
        
        # Calculate signal delay
        signal_delay = receive_time - request.timestamp
        print(f"[RECEIVER] Signal delay: {signal_delay:.2f} seconds")
        
        # Prepare data for visualization
        velocity = (request.velocity_x**2 + request.velocity_y**2 + request.velocity_z**2)**0.5
        telemetry_data = {
            "spacecraft_id": request.spacecraft_id,
            "timestamp": request.timestamp,
            "position_x": request.position_x,
            "position_y": request.position_y,
            "position_z": request.position_z,
            "velocity": velocity,
            "temperature": request.temperature,
            "radiation_level": radiation_level,
            "energy_level": energy_level,
            "mode": mode,
            "alert_level": alert_level,
            "delay": signal_delay
        }
        
        # Send to visualization clients
        self.broadcast_to_visualization(telemetry_data)
        
        return space_telemetry_pb2.TelemetryResponse(
            status="SUCCESS",
            message=f"Telemetry received at {receive_time}"
        )

def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    space_telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(TelemetryReceiver(), server)
    server.add_insecure_port("[::]:50053")
    server.start()
    print(" Receiver gRPC Server Running on Port 50053...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()