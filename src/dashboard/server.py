from flask import Flask, render_template, session
from flask_socketio import SocketIO
import json
import threading
import time
import socket
import datetime
import math

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'space-telemetry-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store recent telemetry for new connections
recent_telemetry = []
MAX_HISTORY = 100  # Increased to store more history

# Store log entries on server side
mission_log = []
MAX_LOG_ENTRIES = 200  # Increased for better history

# Add session persistence
@app.before_request
def ensure_session_data():
    """Initialize session data if not present"""
    if 'visited' not in session:
        session['visited'] = True
        session['first_visit'] = datetime.datetime.now().isoformat()

def add_to_mission_log(message, type='info'):
    """Add an entry to the server-side mission log"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'message': message,
        'type': type
    }
    mission_log.append(log_entry)
    
    # Keep log size manageable
    if len(mission_log) > MAX_LOG_ENTRIES:
        mission_log.pop(0)
    
    # Broadcast to all connected clients
    socketio.emit('log_entry', log_entry)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('[DASHBOARD] Browser client connected')
    # Send recent history on connect
    if recent_telemetry:
        socketio.emit('telemetry_history', recent_telemetry)
        print(f'[DASHBOARD] Sent {len(recent_telemetry)} history items to new client')
    
    # Send mission log history
    if mission_log:
        socketio.emit('log_history', mission_log)
        print(f'[DASHBOARD] Sent {len(mission_log)} log entries to new client')

@socketio.on('disconnect')
def handle_disconnect():
    print('[DASHBOARD] Browser client disconnected')

def receive_telemetry():
    """Connect to receiver and stream telemetry data to clients"""
    global recent_telemetry
    
    # Track last values to detect changes
    last_mode = None
    last_alert = None
    last_energy_level = None  # Track last energy level to detect significant changes
    
    # Add initial log entry
    add_to_mission_log("Telemetry system initialized", "info")
    
    while True:
        try:
            # Connect to receiver socket server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                # Try to connect
                try:
                    print("[DASHBOARD] Connecting to receiver on port 50051...")
                    client_socket.connect(('localhost', 50051))
                    add_to_mission_log("Connected to spacecraft telemetry stream", "info")
                    print("[DASHBOARD] Successfully connected to receiver")
                except Exception as e:
                    print(f"[DASHBOARD] Connection failed: {e}")
                    time.sleep(5)
                    continue
                
                # Buffer for incoming data
                buffer = ""
                
                while True:
                    try:
                        # Receive data
                        data = client_socket.recv(4096)
                        if not data:
                            print("[DASHBOARD] Connection closed by receiver")
                            add_to_mission_log("Lost connection to telemetry stream", "alert")
                            break
                        
                        # Process data
                        buffer += data.decode('utf-8')
                        
                        # Process complete messages
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            
                            try:
                                telemetry_data = json.loads(line)
                                
                                # Skip ping messages
                                if telemetry_data.get('type') == 'ping':
                                    continue
                                
                                # Add bandwidth mode if not present
                                if 'bandwidth_mode' not in telemetry_data:
                                    if telemetry_data.get('alert_level') == 'CRITICAL':
                                        telemetry_data['bandwidth_mode'] = 'critical'
                                    elif telemetry_data.get('alert_level') == 'WARNING':
                                        telemetry_data['bandwidth_mode'] = 'low'
                                    else:
                                        telemetry_data['bandwidth_mode'] = 'normal'
                                
                                # Add orbital information if not present
                                if 'orbit_angle' in telemetry_data:
                                    # Convert orbit angle to percentage 
                                    telemetry_data['orbit_percentage'] = (telemetry_data['orbit_angle'] / (2 * math.pi)) * 100
                                
                                # Store in recent history
                                recent_telemetry.append(telemetry_data)
                                if len(recent_telemetry) > MAX_HISTORY:
                                    recent_telemetry.pop(0)
                                
                                # Check for changes in mode or alert level
                                curr_mode = telemetry_data.get('mode')
                                if curr_mode and curr_mode != last_mode:
                                    add_to_mission_log(f"Spacecraft mode changed to {curr_mode}", "command")
                                    last_mode = curr_mode
                                
                                curr_alert = telemetry_data.get('alert_level')
                                if curr_alert and curr_alert != last_alert:
                                    if curr_alert != 'NOMINAL':
                                        add_to_mission_log(f"Alert level changed to {curr_alert}", "alert")
                                    last_alert = curr_alert
                                
                                # Check for anomalies
                                if telemetry_data.get('anomalies'):
                                    for anomaly in telemetry_data['anomalies']:
                                        add_to_mission_log(f"Anomaly detected: {anomaly}", "alert")
                                
                                # Check energy level
                                energy = telemetry_data.get('energy_level')
                                if energy is not None:
                                    # Log initial energy level
                                    if last_energy_level is None:
                                        last_energy_level = energy
                                    
                                    # Log significant energy changes (more than 5%)
                                    elif abs(energy - last_energy_level) >= 5:
                                        if energy < last_energy_level:
                                            add_to_mission_log(f"Energy decreased to {energy:.1f}%", "info")
                                        else:
                                            add_to_mission_log(f"Energy increased to {energy:.1f}%", "info")
                                        last_energy_level = energy
                                    
                                    # Always log critical energy levels
                                    if energy < 20 and energy > 0 and last_energy_level > 20:
                                        add_to_mission_log(f"Low energy warning: {energy:.1f}%", "alert")
                                    elif energy < 10:
                                        add_to_mission_log(f"CRITICAL: Energy level dangerously low at {energy:.1f}%", "alert")
                                    elif energy == 0:
                                        add_to_mission_log(f"CRITICAL: Spacecraft energy depleted!", "alert")
                                
                                # Broadcast to all connected clients
                                socketio.emit('telemetry_update', telemetry_data)
                                
                            except json.JSONDecodeError:
                                print(f"[DASHBOARD] Invalid JSON: {line}")
                            except Exception as e:
                                print(f"[DASHBOARD] Error processing data: {e}")
                    
                    except Exception as e:
                        print(f"[DASHBOARD] Error receiving data: {e}")
                        break
                
        except Exception as e:
            print(f"[DASHBOARD] Socket error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    # Start telemetry receiver in a separate thread
    telemetry_thread = threading.Thread(target=receive_telemetry, daemon=True)
    telemetry_thread.start()
    
    # Start the Flask server
    print("[DASHBOARD] Starting web server on port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)