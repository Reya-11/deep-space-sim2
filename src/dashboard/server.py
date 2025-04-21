"""
Deep Space Communication Dashboard Server
Provides API endpoints and WebSocket communication for dashboard interface
"""
from flask import Flask, render_template, jsonify, request, abort
from flask_socketio import SocketIO
import json
import threading
import time
import socket
import logging
import random
from datetime import datetime
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dashboard')

# Initialize Flask app and SocketIO
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'space-telemetry-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Telemetry storage
recent_telemetry = {}  # spacecraft_id -> [telemetry_list]
MAX_HISTORY = 100  # per spacecraft

# Anomaly storage
anomaly_history = []  # List of detected anomalies
MAX_ANOMALIES = 200  # Maximum stored anomalies

# Autonomous decisions storage
decision_history = []  # List of autonomous decisions made
MAX_DECISIONS = 100  # Maximum stored decisions

# Server connection settings
RECEIVER_HOST = 'localhost'
RECEIVER_PORTS = 50051  # Primary and backup ports
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_DELAY = 60  # maximum seconds to wait between reconnects

# Connection status
connection_status = {
    "connected": False,
    "last_message": None,
    "reconnect_attempts": 0
}

# SOS status cache
sos_status_cache = {}  # spacecraft_id -> (reason, timestamp)
SOS_CACHE_TTL = 300  # 5 minutes

# ============================================================
# WEB PAGE ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve main dashboard page"""
    return render_template('index.html')

@app.route('/control-panel.html')
def control_panel():
    """Serve control panel page"""
    return render_template('control-panel.html')

@app.route('/favicon.ico')
def favicon():
    """Serve favicon or return no content if missing"""
    return "", 204

# ============================================================
# API ENDPOINTS - TELEMETRY
# ============================================================

@app.route('/api/telemetry/latest')
def latest_telemetry_all():
    """Get latest telemetry for all spacecraft"""
    try:
        if recent_telemetry:
            latest_data = {
                spacecraft_id: telemetry_list[-1] 
                for spacecraft_id, telemetry_list in recent_telemetry.items() 
                if telemetry_list
            }
            return jsonify(latest_data)
        return jsonify({})
    except Exception as e:
        logger.error(f"Error getting latest telemetry: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telemetry/latest/<spacecraft_id>')
def latest_telemetry(spacecraft_id):
    """Get latest telemetry for a specific spacecraft"""
    try:
        if spacecraft_id in recent_telemetry and recent_telemetry[spacecraft_id]:
            return jsonify(recent_telemetry[spacecraft_id][-1])
        return jsonify({}), 404
    except Exception as e:
        logger.error(f"Error getting telemetry for {spacecraft_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telemetry/history')
def telemetry_history_api():
    """Get telemetry history for all spacecraft"""
    try:
        spacecraft_id = request.args.get('spacecraft_id')
        limit = request.args.get('limit', default=MAX_HISTORY, type=int)
        
        if spacecraft_id and spacecraft_id in recent_telemetry:
            # Return history for specific spacecraft
            return jsonify({spacecraft_id: recent_telemetry[spacecraft_id][-limit:]})
        
        # Return all spacecraft history with limits
        limited_history = {
            sc_id: history[-limit:] 
            for sc_id, history in recent_telemetry.items()
        }
        return jsonify(limited_history)
    except Exception as e:
        logger.error(f"Error getting telemetry history: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# API ENDPOINTS - SYSTEM STATUS
# ============================================================

@app.route('/api/system/status')
def system_status_api():
    """Get system status including SOS alerts"""
    try:
        # Check for SOS in the most recent telemetry
        sos_required = False
        sos_reason = ""
        sos_is_new = False  # Add this field
        
        # Check each spacecraft's latest telemetry for SOS
        for spacecraft_id, telemetry_list in recent_telemetry.items():
            if telemetry_list:
                latest = telemetry_list[-1]
                if latest.get('sos_required', False):
                    sos_required = True
                    sos_reason = latest.get('sos_reason', 'Unknown emergency')
                    # Pass through the "is this new" flag
                    sos_is_new = latest.get('sos_is_new', False)
                    break
        
        # Build power level (simulated or from telemetry)
        power_level = 75  # Default
        if recent_telemetry:
            # Get first spacecraft with telemetry
            for telemetry_list in recent_telemetry.values():
                if telemetry_list:
                    # Simulated power level based on timestamp
                    latest = telemetry_list[-1]
                    power_level = min(95, max(20, 75 + (int(latest.get('timestamp', 0) % 20) - 10)))
                    break
        
        return jsonify({
            "power_level": power_level,
            "system_mode": "normal",
            "active_alerts": get_active_alerts(),
            "sos_required": sos_required,
            "sos_reason": sos_reason,
            "sos_is_new": sos_is_new,  # Add this field
            "connection_status": "connected" if connection_status["connected"] else "disconnected",
            "last_update": connection_status["last_message"]
        })
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({
            "power_level": 50,
            "system_mode": "degraded",
            "active_alerts": ["System error"],
            "sos_required": False,
            "sos_reason": "",
            "connection_status": "error",
            "error": str(e)
        }), 500

# ============================================================
# API ENDPOINTS - COMMUNICATION STATS
# ============================================================

@app.route('/api/comm/stats')
def comm_stats_api():
    """Get communication statistics from received telemetry data"""
    try:
        # Calculate statistics from the telemetry data we already have
        total_packets = sum(len(telemetry_list) for telemetry_list in recent_telemetry.values())
        
        # Look through recent telemetry for signal quality data
        signal_quality = None
        signal_delay = None
        data_volume = 0
        
        # Find the most recent telemetry with signal quality info
        for spacecraft_id, telemetry_list in recent_telemetry.items():
            if not telemetry_list:
                continue
                
            # Check the most recent telemetry first
            for telemetry in reversed(telemetry_list):
                # Extract signal quality if available
                if telemetry.get('signal_quality') is not None:
                    signal_quality = telemetry.get('signal_quality')
                    break
                    
                # Some telemetry might have it nested
                if telemetry.get('comm') and telemetry['comm'].get('signal_quality') is not None:
                    signal_quality = telemetry['comm'].get('signal_quality')
                    break
            
            # Estimate data volume based on packet size
            for telemetry in telemetry_list:
                # Rough estimate: JSON size + 20% overhead
                data_volume += len(json.dumps(telemetry)) * 1.2
        
        # Convert to KB
        data_volume_kb = data_volume / 1024
        
        # Estimate packet loss (5-10% is typical for deep space)
        # In real system this would come from the actual receiver, but we'll simulate
        loss_rate = random.uniform(3.0, 8.0)
        packets_lost = int(total_packets * loss_rate / 100)
        
        # Generate statistics
        stats = {
            "packets_sent": total_packets,  # Assuming all telemetry we've received was sent
            "packets_received": total_packets,
            "packets_lost": packets_lost,
            "packet_loss_rate": loss_rate,
            "data_volume_kb": data_volume_kb,
            "signal_quality": signal_quality if signal_quality is not None else random.uniform(85.0, 95.0),
            "signal_delay": signal_delay if signal_delay is not None else random.uniform(0.3, 0.8)
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error generating comm stats: {e}")
        
        # Fallback with reasonable defaults if there's an error
        return jsonify({
            "packets_sent": 100,
            "packets_received": 95,
            "packets_lost": 5,
            "packet_loss_rate": 5.0,
            "data_volume_kb": 150.0,
            "signal_quality": 90.0,
            "signal_delay": 0.5
        })

# ============================================================
# API ENDPOINTS - ANOMALIES AND ALERTS
# ============================================================

@app.route('/api/anomalies')
def anomalies_api():
    """Get detected anomalies"""
    try:
        limit = request.args.get('limit', default=50, type=int)
        spacecraft_id = request.args.get('spacecraft_id', default=None)
        
        if spacecraft_id:
            filtered_anomalies = [
                a for a in anomaly_history 
                if a.get('spacecraft_id') == spacecraft_id
            ]
            return jsonify(filtered_anomalies[-limit:])
            
        return jsonify(anomaly_history[-limit:])
    except Exception as e:
        logger.error(f"Error getting anomalies: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# API ENDPOINTS - SPACECRAFT CONTROL
# ============================================================

@app.route('/api/spacecraft/pause', methods=['POST'])
def pause_spacecraft():
    """Pause or resume a spacecraft"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Invalid request data"}), 400
            
        paused = data.get('paused', False)
        spacecraft_id = data.get('spacecraft_id', None)
        
        # Connect to control server
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.settimeout(2.0)
        control_socket.connect((RECEIVER_HOST, 50055))  # Control port
        
        command = {
            "command": "pause",
            "paused": paused,
            "spacecraft_id": spacecraft_id
        }
        
        # Send command
        control_socket.send(json.dumps(command).encode('utf-8'))
        control_socket.close()
        
        return jsonify({
            "status": "success",
            "paused": paused,
            "spacecraft_id": spacecraft_id
        })
    except Exception as e:
        logger.error(f"Error controlling spacecraft: {e}")
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500

@app.route('/api/spacecraft/list')
def spacecraft_list():
    """Get list of active spacecraft"""
    try:
        return jsonify(list(recent_telemetry.keys()))
    except Exception as e:
        logger.error(f"Error getting spacecraft list: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# API ENDPOINTS - AUTONOMOUS DECISIONS
# ============================================================

@app.route('/api/autonomous/decisions')
def autonomous_decisions_api():
    """Get autonomous decisions made by the spacecraft"""
    try:
        decisions = []
        
        # Get from decision history first
        if decision_history:
            return jsonify(decision_history)
            
        # Look for decisions in telemetry as fallback
        for spacecraft_id, telemetry_list in recent_telemetry.items():
            for telemetry in telemetry_list[-5:]:  # Check last 5 readings
                if telemetry.get('decisions_made') and telemetry.get('decisions_descriptions'):
                    decisions.append({
                        'timestamp': telemetry.get('timestamp', time.time()),
                        'spacecraft_id': spacecraft_id,
                        'decision': telemetry.get('decisions_descriptions', ''),
                        'result': 'Success'  # Assuming success as default
                    })
        
        return jsonify(decisions)
    except Exception as e:
        logger.error(f"Error getting autonomous decisions: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================
# API ENDPOINTS - SPACE WEATHER
# ============================================================

@app.route('/api/space-weather')
def space_weather_api():
    """Get simulated space weather data"""
    try:
        # Generate simulated space weather data
        now = time.time()
        weather = {
            "timestamp": now,
            "solar_flux": 120 + 20 * math.sin(now / 86400 * 2 * math.pi),  # Daily cycle
            "solar_wind_speed": 450 + 50 * math.sin(now / 43200 * 2 * math.pi),  # 12-hour cycle
            "geomagnetic_kp": random.uniform(2, 5),  # Random between 2-5
            "radiation_level": "normal" if random.random() > 0.1 else "elevated",
            "radiation_dose": random.uniform(0.1, 0.5)
        }
        
        # Add solar flare event with 5% probability
        if random.random() < 0.05:
            weather["warnings"] = [{
                "type": "solar_flare",
                "severity": random.choice(["C", "M", "X"]),
                "start_time": now - random.uniform(60, 3600),  # Started 1-60 min ago
                "estimated_end": now + random.uniform(300, 7200),  # Will end in 5-120 min
                "description": "Solar flare detected on Sun's surface"
            }]
        else:
            weather["warnings"] = []
            
        return jsonify(weather)
    except Exception as e:
        logger.error(f"Error generating space weather: {e}")
        return jsonify({
            "timestamp": time.time(),
            "solar_flux": 110,
            "solar_wind_speed": 400,
            "geomagnetic_kp": 2.0,
            "radiation_level": "normal",
            "radiation_dose": 0.1,
            "warnings": []
        })

# ============================================================
# SOCKETIO EVENT HANDLERS
# ============================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info('Client connected')
    # Send recent history on connect
    if recent_telemetry:
        socketio.emit('telemetry_history', recent_telemetry)
    
    # Send spacecraft list
    socketio.emit('spacecraft_list', list(recent_telemetry.keys()))
    
    # Send recent anomalies
    if anomaly_history:
        socketio.emit('anomaly_history', anomaly_history[-20:])

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected')

@socketio.on('request_history')
def handle_history_request(data):
    """Handle client request for specific history"""
    try:
        spacecraft_id = data.get('spacecraft_id')
        if spacecraft_id and spacecraft_id in recent_telemetry:
            socketio.emit('telemetry_history', {
                spacecraft_id: recent_telemetry[spacecraft_id]
            })
    except Exception as e:
        logger.error(f"Error handling history request: {e}")

# ============================================================
# TELEMETRY PROCESSING FUNCTIONS
# ============================================================

def check_for_anomalies(telemetry):
    """Detect if telemetry contains anomalous values"""
    # Temperature anomalies
    if "temperature" in telemetry:
        temp = telemetry["temperature"]
        if temp < -40 or temp > 40:
            return True
    
    # Position anomalies
    if all(k in telemetry for k in ["position_x", "position_y", "position_z"]):
        # Calculate distance from origin
        x, y, z = telemetry["position_x"], telemetry["position_y"], telemetry["position_z"]
        distance = (x**2 + y**2 + z**2)**0.5
        
        # Check if too far or too close
        if distance > 2e8 or distance < 1e6:  # 200M km or 1000 km
            return True
    
    # Velocity anomalies
    if all(k in telemetry for k in ["velocity_x", "velocity_y", "velocity_z"]):
        vx, vy, vz = telemetry["velocity_x"], telemetry["velocity_y"], telemetry["velocity_z"]
        velocity = (vx**2 + vy**2 + vz**2)**0.5
        
        # Check if too fast
        if velocity > 30000:  # 30 km/s
            return True
    
    return False

def is_critical_anomaly(telemetry):
    """Check if anomaly is critical severity"""
    # Temperature critical
    if "temperature" in telemetry:
        temp = telemetry["temperature"]
        if temp < -80 or temp > 80:
            return True
    
    # Extreme distance
    if all(k in telemetry for k in ["position_x", "position_y", "position_z"]):
        x, y, z = telemetry["position_x"], telemetry["position_y"], telemetry["position_z"]
        distance = (x**2 + y**2 + z**2)**0.5
        if distance > 5e8 or distance < 5e5:  # 500M km or 500 km
            return True
    
    # Extreme velocity
    if all(k in telemetry for k in ["velocity_x", "velocity_y", "velocity_z"]):
        vx, vy, vz = telemetry["velocity_x"], telemetry["velocity_y"], telemetry["velocity_z"]
        velocity = (vx**2 + vy**2 + vz**2)**0.5
        if velocity > 50000:  # 50 km/s
            return True
    
    return False

def get_anomaly_description(telemetry):
    """Generate descriptive message for the anomaly"""
    messages = []
    
    # Temperature anomalies
    if "temperature" in telemetry:
        temp = telemetry["temperature"]
        if temp < -80:
            messages.append(f"CRITICAL: Extreme low temperature: {temp:.1f}°C")
        elif temp < -40:
            messages.append(f"WARNING: Low temperature: {temp:.1f}°C")
        elif temp > 80:
            messages.append(f"CRITICAL: Extreme high temperature: {temp:.1f}°C")
        elif temp > 40:
            messages.append(f"WARNING: High temperature: {temp:.1f}°C")
    
    # Position anomalies
    if all(k in telemetry for k in ["position_x", "position_y", "position_z"]):
        x, y, z = telemetry["position_x"], telemetry["position_y"], telemetry["position_z"]
        distance = (x**2 + y**2 + z**2)**0.5
        
        if distance > 5e8:
            messages.append(f"CRITICAL: Spacecraft too distant: {distance/1e6:.1f}M km")
        elif distance > 2e8:
            messages.append(f"WARNING: Spacecraft distance exceeds expected range: {distance/1e6:.1f}M km")
        elif distance < 5e5:
            messages.append(f"CRITICAL: Spacecraft too close to Earth: {distance/1000:.1f} km")
        elif distance < 1e6:
            messages.append(f"WARNING: Spacecraft distance below safe threshold: {distance/1000:.1f} km")
    
    # Velocity anomalies
    if all(k in telemetry for k in ["velocity_x", "velocity_y", "velocity_z"]):
        vx, vy, vz = telemetry["velocity_x"], telemetry["velocity_y"], telemetry["velocity_z"]
        velocity = (vx**2 + vy**2 + vz**2)**0.5
        
        if velocity > 50000:
            messages.append(f"CRITICAL: Extreme velocity detected: {velocity/1000:.2f} km/s")
        elif velocity > 30000:
            messages.append(f"WARNING: High velocity detected: {velocity/1000:.2f} km/s")
    
    if messages:
        return messages[0]  # Return first (most critical) message
    
    return "Unknown anomaly detected"

def is_new_anomaly(new_anomaly, last_anomaly):
    """Check if this is a new anomaly, not a duplicate of the last one"""
    # If more than 10 seconds apart, consider it new
    time_diff = abs(new_anomaly.get('timestamp', 0) - last_anomaly.get('timestamp', 0))
    if time_diff > 10:
        return True
    
    # Different spacecraft always counts as new
    if new_anomaly.get('spacecraft_id') != last_anomaly.get('spacecraft_id'):
        return True
    
    # Same message + same severity + same spacecraft = duplicate
    if (new_anomaly.get('message') == last_anomaly.get('message') and
        new_anomaly.get('severity') == last_anomaly.get('severity')):
        return False
    
    return True

def get_active_alerts():
    """Get current active alerts from recent anomalies"""
    active = []
    now = time.time()
    
    # Look at recent anomalies (last 5 minutes)
    for anomaly in anomaly_history:
        timestamp = anomaly.get('timestamp', 0)
        if now - timestamp < 300:  # 5 minutes
            if anomaly.get('severity') == 'critical':
                alert = f"CRITICAL: {anomaly.get('message')}"
                if alert not in active:
                    active.append(alert)
    
    return active

# ============================================================
# TELEMETRY CONNECTION HANDLING
# ============================================================

def calculate_backoff():
    """Calculate reconnection backoff time"""
    attempt = min(connection_status["reconnect_attempts"], 10)
    delay = min(RECONNECT_DELAY * (2 ** attempt), MAX_RECONNECT_DELAY)
    jitter = random.uniform(0, min(delay * 0.2, 5))  # Add up to 20% jitter, max 5 sec
    return delay + jitter

def receive_telemetry():
    """Connect to receiver and stream telemetry data to clients"""
    global recent_telemetry, anomaly_history, decision_history, connection_status
    
    logger.info("Starting telemetry receiver thread")
    
    while True:
        # Pick port to try (alternate if we've been failing)
        port = RECEIVER_PORTS
        
        try:
            # Connect to receiver socket server
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(10.0)  # 10 second timeout
            client_socket.connect((RECEIVER_HOST, port))
            
            logger.info(f"Connected to receiver on port {port}")
            connection_status["connected"] = True
            connection_status["reconnect_attempts"] = 0
            
            # Buffer for incoming data
            buffer = ""
            
            # Send ping request to check connection
            ping_request = json.dumps({"request": "ping"}) + "\n"
            client_socket.send(ping_request.encode('utf-8'))
            
            while True:
                # Receive data
                data = client_socket.recv(4096)
                if not data:
                    logger.warning("Connection to receiver lost (empty data)")
                    connection_status["connected"] = False
                    break
                
                # Record last message time
                connection_status["last_message"] = datetime.now().isoformat()
                
                # Add to buffer and process complete messages
                buffer += data.decode('utf-8')
                
                while '\n' in buffer:
                    # Extract message up to newline
                    message_end = buffer.index('\n')
                    message = buffer[:message_end]
                    buffer = buffer[message_end + 1:]
                    print("message", message)
                    # Process message
                    try:
                        telemetry_data = json.loads(message)
                        
                        # Skip ping messages
                        if telemetry_data.get('type') == 'ping':
                            continue
                        
                        # Get spacecraft ID
                        spacecraft_id = telemetry_data.get("spacecraft_id", "unknown")
                        
                        # Initialize list for this spacecraft if needed
                        if spacecraft_id not in recent_telemetry:
                            recent_telemetry[spacecraft_id] = []
                            
                        # Add to history for this spacecraft
                        recent_telemetry[spacecraft_id].append(telemetry_data)
                        
                        # Trim history if needed
                        if len(recent_telemetry[spacecraft_id]) > MAX_HISTORY:
                            recent_telemetry[spacecraft_id].pop(0)
                            
                        # Broadcast to all connected clients
                        socketio.emit('telemetry_update', telemetry_data)
                        
                        # Also emit a spacecraft list update
                        spacecraft_list = list(recent_telemetry.keys())
                        socketio.emit('spacecraft_list', spacecraft_list)
                        
                        # Process anomalies from telemetry directly
                        if telemetry_data.get("anomaly_detected", False):
                            # Extract anomalies from telemetry message from edge_processing.py
                            descriptions = telemetry_data.get("anomaly_descriptions", "")
                            if descriptions:
                                desc_list = descriptions.split(";") if isinstance(descriptions, str) else descriptions
                                severity = telemetry_data.get("anomaly_severity", "warning")
                                
                                for description in desc_list:
                                    if not description or not isinstance(description, str) or not description.strip():
                                        continue
                                        
                                    anomaly = {
                                        "timestamp": telemetry_data.get("timestamp", time.time()),
                                        "spacecraft_id": spacecraft_id,
                                        "severity": severity,
                                        "message": description.strip()
                                    }
                                    
                                    # Only add if it's not a duplicate
                                    if not anomaly_history or is_new_anomaly(anomaly, anomaly_history[-1]):
                                        anomaly_history.append(anomaly)
                                        logger.info(f"Adding anomaly: {anomaly['message']}")
                                        
                                        # Emit the new anomaly to connected clients
                                        socketio.emit('new_anomaly', anomaly)
                                        
                                        # Limit history size
                                        if len(anomaly_history) > MAX_ANOMALIES:
                                            anomaly_history.pop(0)
                        
                        # Keep existing detection as fallback
                        elif check_for_anomalies(telemetry_data):
                            # Create a meaningful anomaly record with no duplicates
                            anomaly = {
                                "timestamp": telemetry_data.get("timestamp", time.time()),
                                "spacecraft_id": spacecraft_id,
                                "severity": "critical" if is_critical_anomaly(telemetry_data) else "warning",
                                "message": get_anomaly_description(telemetry_data)
                            }
                            
                            # Only add if it's not a duplicate of the most recent anomaly
                            if not anomaly_history or is_new_anomaly(anomaly, anomaly_history[-1]):
                                logger.info(f"Adding server-detected anomaly: {anomaly['message']}")
                                anomaly_history.append(anomaly)
                                
                                # Emit the new anomaly
                                socketio.emit('new_anomaly', anomaly)
                                
                                # Limit history size
                                if len(anomaly_history) > MAX_ANOMALIES:
                                    anomaly_history.pop(0)
                                    
                        # Process autonomous decisions
                        if telemetry_data.get("decisions_made") and telemetry_data.get("decisions_descriptions"):
                            try:
                                decisions_raw = telemetry_data.get("decisions_descriptions")
                                
                                # Handle both string and list formats
                                if isinstance(decisions_raw, str):
                                    decisions_list = [decisions_raw]
                                elif isinstance(decisions_raw, list):
                                    decisions_list = decisions_raw
                                else:
                                    # Try to parse JSON if it's a JSON string
                                    try:
                                        decisions_list = json.loads(decisions_raw)
                                        if not isinstance(decisions_list, list):
                                            decisions_list = [str(decisions_list)]
                                    except:
                                        decisions_list = [str(decisions_raw)]
                                
                                # Process each decision
                                for decision in decisions_list:
                                    new_decision = {
                                        'timestamp': telemetry_data.get("timestamp", time.time()),
                                        'spacecraft_id': spacecraft_id,
                                        'decision': decision,
                                        'result': 'Success'
                                    }
                                    
                                    # Add to history
                                    decision_history.append(new_decision)
                                    
                                    # Emit to clients
                                    socketio.emit('new_decision', new_decision)
                                    
                                    # Limit history size
                                    if len(decision_history) > MAX_DECISIONS:
                                        decision_history.pop(0)
                                        
                            except Exception as e:
                                logger.error(f"Error processing decisions: {e}")
                                
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {message}")
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        
        except (ConnectionRefusedError, socket.error, socket.timeout) as e:
            # Connection failed
            logger.error(f"Could not connect to receiver on port {port}: {e}")
            connection_status["connected"] = False
            connection_status["reconnect_attempts"] += 1
            
            # Calculate backoff time
            backoff = calculate_backoff()
            logger.info(f"Retrying in {backoff:.1f} seconds... (Attempt {connection_status['reconnect_attempts']})")
            time.sleep(backoff)
            
        finally:
            # Clean up socket
            try:
                client_socket.close()
            except:
                pass

# ============================================================
# SERVER STARTUP
# ============================================================

def run_server():
    """Start the Flask+SocketIO server"""
    # More robust telemetry thread start
    print("Starting telemetry receiver thread...")
    try:
        telemetry_thread = threading.Thread(target=receive_telemetry, daemon=True)
        telemetry_thread.start()
        print(f"Telemetry thread started successfully: {telemetry_thread.is_alive()}")
    except Exception as e:
        print(f"ERROR STARTING TELEMETRY THREAD: {e}")
        import traceback
        traceback.print_exc()
    
    # Start the Flask server
    logger.info("Starting Flask server on port 5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    run_server()