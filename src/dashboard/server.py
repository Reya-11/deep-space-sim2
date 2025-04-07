# dashboard/server.py
from flask import Flask, render_template
from flask_socketio import SocketIO
import json
import threading
import time
import socket

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'space-telemetry-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store recent telemetry for new connections
recent_telemetry = []
MAX_HISTORY = 50

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('[VISUALIZATION] Client connected')
    # Send recent history on connect
    if recent_telemetry:
        socketio.emit('telemetry_history', recent_telemetry)

@socketio.on('disconnect')
def handle_disconnect():
    print('[VISUALIZATION] Client disconnected')

def receive_telemetry():
    """Connect to receiver and stream telemetry data to clients"""
    global recent_telemetry
    
    while True:
        try:
            # Connect to receiver socket server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(('localhost', 50054))
            print("[VISUALIZATION] Connected to receiver")
            
            # Buffer for incoming data
            buffer = ""
            
            while True:
                # Receive data
                data = client_socket.recv(4096)
                if not data:
                    print("[VISUALIZATION] Connection to receiver lost")
                    break
                
                # Add to buffer and process complete messages
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    # Extract message up to newline
                    message_end = buffer.index('\n')
                    message = buffer[:message_end]
                    buffer = buffer[message_end + 1:]
                    
                    # Process message
                    try:
                        telemetry_data = json.loads(message)
                        
                        # Skip ping messages
                        if telemetry_data.get('type') == 'ping':
                            continue
                            
                        # Store in recent history
                        recent_telemetry.append(telemetry_data)
                        if len(recent_telemetry) > MAX_HISTORY:
                            recent_telemetry.pop(0)
                            
                        # Broadcast to all connected clients
                        socketio.emit('telemetry_update', telemetry_data)
                        print(f"[VISUALIZATION] Broadcasted telemetry: {telemetry_data['spacecraft_id']} @ {telemetry_data['timestamp']}")
                    except json.JSONDecodeError:
                        print(f"[VISUALIZATION] Invalid JSON received: {message}")
                    except Exception as e:
                        print(f"[VISUALIZATION] Error processing message: {e}")
        
        except (ConnectionRefusedError, socket.error) as e:
            print(f"[VISUALIZATION] Could not connect to receiver: {e}")
            print("[VISUALIZATION] Retrying in 5 seconds...")
            time.sleep(5)
        finally:
            try:
                client_socket.close()
            except:
                pass

def run_server():
    """Start the Flask+SocketIO server"""
    # Start telemetry receiver in a separate thread
    telemetry_thread = threading.Thread(target=receive_telemetry, daemon=True)
    telemetry_thread.start()
    
    # Start the Flask server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)

if __name__ == '__main__':
    run_server()