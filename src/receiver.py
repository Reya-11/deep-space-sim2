import grpc
from concurrent import futures
import sqlite3
import time
import space_telemetry_pb2 as telemetry_pb2
import space_telemetry_pb2_grpc as telemetry_pb2_grpc
import threading
import socket
import json

DB_FILE = "telemetry_data.db"

# Socket for streaming data to the visualization
visualization_socket = None

class ReceiverService(telemetry_pb2_grpc.TelemetryServiceServicer):
    def SendTelemetry(self, request, context):
        print(f"[RECEIVER] Received telemetry: {request.spacecraft_id} @ {request.timestamp}")
        
        # Save to database
        save_to_db(request)
        
        # Process and stream data to visualization
        telemetry_data = {
            "spacecraft_id": request.spacecraft_id,
            "timestamp": request.timestamp,
            "position_x": request.position_x,
            "position_y": request.position_y,
            "position_z": request.position_z,
            "velocity_x": request.velocity_x,
            "velocity_y": request.velocity_y,
            "velocity_z": request.velocity_z,
            "temperature": request.temperature,
            "altitude": calculate_altitude(request.position_x, request.position_y, request.position_z),
            "velocity": calculate_velocity(request.velocity_x, request.velocity_y, request.velocity_z)
        }
        
        # Stream to visualization
        stream_to_visualization(telemetry_data)

        return telemetry_pb2.TelemetryResponse(status="Received")

def save_to_db(data):
    """Save telemetry data to SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
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
    cursor.execute("""
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

def calculate_altitude(x, y, z):
    """Calculate altitude based on position coordinates"""
    return round(((x**2 + y**2 + z**2)**0.5) / 1000, 2)  # in km

def calculate_velocity(vx, vy, vz):
    """Calculate velocity magnitude from vector components"""
    return round(((vx**2 + vy**2 + vz**2)**0.5), 2)  # in m/s

def stream_to_visualization(data):
    """Stream telemetry data to visualization server via socket"""
    global visualization_socket
    
    if visualization_socket is None:
        # Visualization server not connected yet
        return
    
    try:
        # Convert data to JSON and add newline as message delimiter
        message = json.dumps(data) + "\n"
        visualization_socket.sendall(message.encode('utf-8'))
    except (BrokenPipeError, ConnectionResetError):
        print("[RECEIVER] Visualization connection lost. Waiting for reconnection...")
        visualization_socket = None

def visualization_server():
    """Socket server to accept connections from visualization client"""
    global visualization_socket
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', 50054))
    server_socket.listen(1)
    
    print("[RECEIVER] Visualization socket server started on port 50054")
    
    while True:
        # Accept connection from visualization
        if visualization_socket is None:
            conn, addr = server_socket.accept()
            visualization_socket = conn
            print(f"[RECEIVER] Visualization connected from {addr}")
        
        # Check if connection is still alive
        try:
            time.sleep(5)
            # Send heartbeat/ping
            if visualization_socket:
                visualization_socket.sendall(b'{"type":"ping"}\n')
        except (BrokenPipeError, ConnectionResetError):
            print("[RECEIVER] Visualization disconnected")
            visualization_socket = None

def serve():
    """Start the gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(ReceiverService(), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    print("[RECEIVER] gRPC server started on port 50053")
    
    # Start visualization socket server in a separate thread
    viz_thread = threading.Thread(target=visualization_server, daemon=True)
    viz_thread.start()
    
    server.wait_for_termination()

if __name__ == '__main__':
    serve()