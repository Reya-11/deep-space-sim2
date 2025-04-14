import grpc
from concurrent import futures
import time
import sys
import zlib
import json
import random
import math
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

class DeepSpaceCommSimulator:
    def __init__(self, distance_au=10.0):
        """
        Initialize communication simulator
        
        Args:
            distance_au: Distance in Astronomical Units (1 AU = distance from Earth to Sun)
        """
        self.distance_au = distance_au
        self.light_speed = 299792458  # m/s
        self.au_in_meters = 149597870700  # meters
        
        # Signal quality parameters
        self.base_bit_error_rate = 0.0001  # Base error rate
        self.solar_interference = 0.0  # 0.0 to 1.0
        
    def set_distance(self, distance_au):
        """Set distance in Astronomical Units"""
        self.distance_au = distance_au
        
    def set_solar_interference(self, level):
        """Set solar interference level (0.0 to 1.0)"""
        self.solar_interference = max(0, min(1, level))
    
    def calculate_delay(self):
        """Calculate one-way signal delay in seconds"""
        distance_meters = self.distance_au * self.au_in_meters
        delay_seconds = distance_meters / self.light_speed
        
        # For simulation purposes, scale this down to make it usable
        # 1 AU takes about 8.3 minutes for light to travel
        # We'll scale that to 0.5 seconds for usability
        scaled_delay = delay_seconds * 0.001  # Scale factor
        
        return scaled_delay
    
    def apply_delay(self):
        """Apply realistic transmission delay"""
        delay = self.calculate_delay()
        time.sleep(delay)
        
    def apply_two_way_delay(self):
        """Apply realistic round-trip delay (send + receive)"""
        delay = self.calculate_delay() * 2
        time.sleep(delay)
        
    def introduce_random_delay(self):
        """Introduce random additional delay to simulate processing time"""
        random_delay = random.uniform(0, 0.5)  # Up to 500ms additional delay
        time.sleep(random_delay)
        
    def simulate_packet_loss(self):
        """Simulate packet loss. Returns True if packet should be considered lost."""
        # Base probability of packet loss
        loss_probability = 0.01  # 1% base loss rate
        
        # Increase with distance and solar interference
        distance_factor = min(1, self.distance_au / 50)  # Max effect at 50 AU
        total_probability = loss_probability + (0.1 * distance_factor) + (0.2 * self.solar_interference)
        
        return random.random() < total_probability
    
    def apply_noise(self, data):
        """Apply realistic noise to data"""
        # Only applies to numeric data
        if isinstance(data, (int, float)):
            # Calculate error magnitude based on distance and interference
            error_magnitude = 0.01 * (1 + self.distance_au/30.0 + self.solar_interference*2)
            noise = random.normalvariate(0, data * error_magnitude) if data != 0 else random.normalvariate(0, 0.1)
            return data + noise
        return data
    
    def simulate_bandwidth_constraint(self, data_size_bytes, bandwidth_bps=32):
        """
        Simulate bandwidth constraints by calculating transmission time
        
        Args:
            data_size_bytes: Size of data in bytes
            bandwidth_bps: Bandwidth in bits per second
            
        Returns:
            Transmission time in seconds
        """
        # Convert bytes to bits
        data_size_bits = data_size_bytes * 8
        
        # Calculate transmission time
        transmission_time = data_size_bits / bandwidth_bps
        
        # Scale for simulation purposes
        scaled_time = transmission_time * 0.01
        
        return scaled_time

class TelemetryCompressor:
    def __init__(self):
        # Define priorities for different telemetry fields
        self.field_priorities = {
            "spacecraft_id": "critical",
            "timestamp": "critical", 
            "temperature": "high",
            "position_x": "medium",
            "position_y": "medium",
            "position_z": "medium",
            "velocity_x": "low",
            "velocity_y": "low", 
            "velocity_z": "low",
            "radiation_level": "medium",
            "energy_level": "high",
            "mode": "high"
        }
        
        self.precision = {
            "high": 4,     # 4 decimal places
            "medium": 2,   # 2 decimal places
            "low": 1       # 1 decimal place
        }
        
    def compress_telemetry(self, telemetry_data, bandwidth_mode="normal"):
        """
        Compress telemetry data based on bandwidth mode
        
        Args:
            telemetry_data: The telemetry data object
            bandwidth_mode: "critical" (minimal data), "low", "normal", "high" (all data)
            
        Returns:
            Compressed data as bytes
        """
        # Convert to dictionary for easier manipulation
        data_dict = {}
        for field, value in telemetry_data.ListFields():
            data_dict[field.name] = value
            
        # Filter and prioritize fields based on bandwidth mode
        filtered_data = {}
        
        if bandwidth_mode == "critical":
            # Only send critical fields
            for field, priority in self.field_priorities.items():
                if priority == "critical" and field in data_dict:
                    filtered_data[field] = data_dict[field]
                    
        elif bandwidth_mode == "low":
            # Send critical and high priority fields
            for field, priority in self.field_priorities.items():
                if priority in ["critical", "high"] and field in data_dict:
                    filtered_data[field] = data_dict[field]
                    
        elif bandwidth_mode == "normal":
            # Send all but low priority fields
            for field, priority in self.field_priorities.items():
                if priority != "low" and field in data_dict:
                    filtered_data[field] = data_dict[field]
                    
        else:  # high bandwidth mode
            filtered_data = data_dict
            
        # Apply precision rounding to numeric fields
        for field, value in filtered_data.items():
            if isinstance(value, float):
                priority = self.field_priorities.get(field, "medium")
                if priority in self.precision:
                    filtered_data[field] = round(value, self.precision[priority])
                    
        # Convert to JSON
        json_data = json.dumps(filtered_data)
        
        # Compress with zlib
        compressed = zlib.compress(json_data.encode('utf-8'))
        
        compression_ratio = len(compressed) / len(json_data)
        print(f"[COMPRESSION] Ratio: {compression_ratio:.2f}, Original: {len(json_data)} bytes, Compressed: {len(compressed)} bytes")
        
        return compressed

    def decompress_telemetry(self, compressed_data):
        """
        Decompress telemetry data
        
        Args:
            compressed_data: zlib compressed data
            
        Returns:
            Original JSON data as dictionary
        """
        # Decompress with zlib
        decompressed = zlib.decompress(compressed_data)
        
        # Parse JSON
        data_dict = json.loads(decompressed.decode('utf-8'))
        
        return data_dict

class MissionControl:
    """Mission control logic for autonomous decision making"""
    
    def __init__(self):
        # Define safe operating parameters
        self.safe_params = {
            'temperature_min': -50,
            'temperature_max': 50,
            'velocity_max': 15,  # m/s
            'position_change_max': 50,  # max acceptable position change between readings
            'radiation_max': 1000,
            'energy_min': 30,  # minimum safe energy level
            'critical_energy': 15  # critical energy level
        }
        
        # Tracking data
        self.spacecraft_history = {}  # Track data for each spacecraft
        self.command_history = {}     # Track commands sent to each spacecraft
        
        # Science opportunities
        self.science_targets = [
            {'name': 'Interesting Nebula', 'position': (5000, 2000, 3000), 'active': True},
            {'name': 'Unusual Asteroid', 'position': (-2000, -1000, 4000), 'active': True},
            {'name': 'Radiation Anomaly', 'position': (1000, -3000, 2000), 'active': True}
        ]
    
    def track_spacecraft(self, telemetry):
        """Track spacecraft data over time"""
        spacecraft_id = telemetry.spacecraft_id
        
        if spacecraft_id not in self.spacecraft_history:
            self.spacecraft_history[spacecraft_id] = {
                'positions': [],
                'temperatures': [],
                'energy_levels': [],
                'modes': [],
                'last_command_time': 0,
                'anomaly_count': 0
            }
        
        # Add current data to history
        history = self.spacecraft_history[spacecraft_id]
        history['positions'].append((telemetry.position_x, telemetry.position_y, telemetry.position_z))
        history['temperatures'].append(telemetry.temperature)
        
        # Add optional attributes if they exist
        if hasattr(telemetry, 'energy_level'):
            history['energy_levels'].append(telemetry.energy_level)
        else:
            history['energy_levels'].append(100)  # Default value
            
        if hasattr(telemetry, 'mode'):
            history['modes'].append(telemetry.mode)
        else:
            history['modes'].append('NORMAL')  # Default mode
        
        # Keep history manageable
        max_history = 100
        if len(history['positions']) > max_history:
            history['positions'] = history['positions'][-max_history:]
            history['temperatures'] = history['temperatures'][-max_history:]
            history['energy_levels'] = history['energy_levels'][-max_history:]
            history['modes'] = history['modes'][-max_history:]
    
    def make_decision(self, telemetry, anomalies):
        """
        Make autonomous decisions based on telemetry data
        
        Returns a list of commands to send to the spacecraft
        """
        spacecraft_id = telemetry.spacecraft_id
        commands = []
        
        # Track this telemetry data
        self.track_spacecraft(telemetry)
        
        # Get spacecraft history
        history = self.spacecraft_history.get(spacecraft_id, {})
        current_time = time.time()
        
        # Don't send commands too frequently
        if history.get('last_command_time', 0) > current_time - 10:  # 10-second cooldown
            return commands
            
        # Current spacecraft state
        current_mode = telemetry.mode if hasattr(telemetry, 'mode') else 'NORMAL'
        energy_level = telemetry.energy_level if hasattr(telemetry, 'energy_level') else 100
        position = (telemetry.position_x, telemetry.position_y, telemetry.position_z)
        
        # Handle critical anomalies first
        if anomalies:
            history['anomaly_count'] = history.get('anomaly_count', 0) + 1
            
            # If multiple anomalies or critical conditions, enter safe mode
            if (len(anomalies) > 1 or 
                history['anomaly_count'] >= 3 or 
                energy_level <= self.safe_params['critical_energy'] or
                any('critical' in anomaly.lower() for anomaly in anomalies)):
                
                if current_mode != 'SAFE':
                    print(f"[MISSION CONTROL] CRITICAL SITUATION: Commanding {spacecraft_id} to enter SAFE mode")
                    commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "SAFE"}))
                    history['last_command_time'] = current_time
                    return commands  # Critical command takes precedence
        else:
            # Reset anomaly counter when no anomalies
            history['anomaly_count'] = max(0, history.get('anomaly_count', 0) - 1)
        
        # Energy management decisions
        if energy_level <= self.safe_params['energy_min'] and current_mode != 'SAFE':
            print(f"[MISSION CONTROL] Low energy detected: Commanding {spacecraft_id} to enter SAFE mode")
            commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "SAFE"}))
        
        # If in SAFE mode but energy recovered, return to NORMAL
        elif current_mode == 'SAFE' and energy_level > 60 and history.get('anomaly_count', 0) == 0:
            print(f"[MISSION CONTROL] Energy restored: Commanding {spacecraft_id} to return to NORMAL mode")
            commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "NORMAL"}))
        
        # Temperature management
        if hasattr(telemetry, 'temperature'):
            if telemetry.temperature > 40 and telemetry.temperature < self.safe_params['temperature_max']:
                print(f"[MISSION CONTROL] High temperature warning: Commanding thermal management")
                commands.append(self._create_command(spacecraft_id, "THERMAL_CONTROL", {"action": "COOLING"}))
            elif telemetry.temperature < -40 and telemetry.temperature > self.safe_params['temperature_min']:
                print(f"[MISSION CONTROL] Low temperature warning: Commanding thermal management")
                commands.append(self._create_command(spacecraft_id, "THERMAL_CONTROL", {"action": "HEATING"}))
        
        # Science opportunity detection
        if current_mode in ['NORMAL', 'SCIENCE'] and energy_level > 70:
            for target in self.science_targets:
                if target['active']:
                    # Calculate distance to science target
                    distance = math.sqrt(
                        (position[0] - target['position'][0])**2 +
                        (position[1] - target['position'][1])**2 +
                        (position[2] - target['position'][2])**2
                    )
                    
                    # If spacecraft is near a science target
                    if distance < 1000:  # Within range
                        if current_mode != 'SCIENCE':
                            print(f"[MISSION CONTROL] Science opportunity detected: {target['name']}")
                            commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "SCIENCE"}))
                            break
                    elif current_mode == 'SCIENCE' and random.random() < 0.2:  # 20% chance to complete science mode
                        print(f"[MISSION CONTROL] Science observation complete")
                        commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "NORMAL"}))
                        break
        
        # Scheduled maintenance (every 5 minutes)
        last_maintenance = history.get('last_maintenance', 0)
        if (current_time - last_maintenance > 300 and  # 5 minutes
            current_mode != 'SAFE' and 
            current_mode != 'MAINTENANCE' and 
            energy_level > 60):
            print(f"[MISSION CONTROL] Scheduling maintenance for {spacecraft_id}")
            commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "MAINTENANCE"}))
            history['last_maintenance'] = current_time
        
        # Return from maintenance mode after 30 seconds
        if current_mode == 'MAINTENANCE' and history.get('last_maintenance', 0) < current_time - 30:
            print(f"[MISSION CONTROL] Maintenance complete for {spacecraft_id}")
            commands.append(self._create_command(spacecraft_id, "MODE_CHANGE", {"mode": "NORMAL"}))
        
        # Update last command time if commands were generated
        if commands:
            history['last_command_time'] = current_time
        
        return commands
    
    def _create_command(self, spacecraft_id, command_type, parameters):
        """Create a command object"""
        command = space_telemetry_pb2.Command(
            spacecraft_id=spacecraft_id,
            command_type=command_type,
            timestamp=time.time()
        )
        
        for key, value in parameters.items():
            command.parameters[key] = str(value)
            
        # Track command in history
        if spacecraft_id not in self.command_history:
            self.command_history[spacecraft_id] = []
            
        self.command_history[spacecraft_id].append({
            'type': command_type,
            'params': parameters,
            'time': time.time()
        })
        
        return command

class TelemetryProcessor(space_telemetry_pb2_grpc.TelemetryServiceServicer):
    def __init__(self):
        # Define anomaly thresholds
        self.thresholds = {
            'temperature_min': -50,
            'temperature_max': 50,
            'velocity_max': 15,  # m/s
            'position_change_max': 50,  # max change between readings
            'radiation_max': 1000  # example additional parameter
        }
        self.last_position = {}  # Track positions by spacecraft ID
        self.anomaly_count = {}  # Track anomalies by spacecraft ID
        self.alert_levels = {}   # Track alert levels by spacecraft ID
        
        # Initialize communication simulator
        self.comm_simulator = DeepSpaceCommSimulator(distance_au=10.0)
        
        # Initialize compressor
        self.compressor = TelemetryCompressor()
        
        # Initialize mission control system for decision making
        self.mission_control = MissionControl()
        
        # Bandwidth mode starts as normal
        self.bandwidth_mode = "normal"
        
    def SendTelemetry(self, request, context):
        # Simulate receiving delay
        self.comm_simulator.apply_delay()
        spacecraft_id = request.spacecraft_id
        
        print(f"[EDGE] Received telemetry: {spacecraft_id} @ {request.timestamp}")
        print(f"[EDGE] Signal delay: {self.comm_simulator.calculate_delay():.2f} seconds")
        
        # Apply noise to telemetry values
        processed_telemetry = space_telemetry_pb2.TelemetryData(
            spacecraft_id=spacecraft_id,
            timestamp=request.timestamp,
            position_x=self.comm_simulator.apply_noise(request.position_x + 1),
            position_y=self.comm_simulator.apply_noise(request.position_y + 1),
            position_z=self.comm_simulator.apply_noise(request.position_z + 1),
            velocity_x=self.comm_simulator.apply_noise(request.velocity_x),
            velocity_y=self.comm_simulator.apply_noise(request.velocity_y),
            velocity_z=self.comm_simulator.apply_noise(request.velocity_z),
            temperature=self.comm_simulator.apply_noise(request.temperature)
        )
        
        # If the incoming telemetry has the new fields, copy them over
        if hasattr(request, 'radiation_level'):
            processed_telemetry.radiation_level = self.comm_simulator.apply_noise(request.radiation_level)
        if hasattr(request, 'energy_level'):
            processed_telemetry.energy_level = request.energy_level
        if hasattr(request, 'mode'):
            processed_telemetry.mode = request.mode

        # Get last position for this spacecraft
        if spacecraft_id not in self.last_position:
            self.last_position[spacecraft_id] = (0, 0, 0)
            self.anomaly_count[spacecraft_id] = 0
            self.alert_levels[spacecraft_id] = "NOMINAL"

        # Detect anomalies
        anomalies = self.detect_anomalies(processed_telemetry)
        
        if anomalies:
            self.anomaly_count[spacecraft_id] += 1
            print(f"[EDGE] Anomalies detected for {spacecraft_id}: {', '.join(anomalies)}")
            
            # Update alert level based on anomaly count
            if self.anomaly_count[spacecraft_id] > 5:
                self.alert_levels[spacecraft_id] = "CRITICAL"
                print(f"[EDGE] ALERT: Critical anomaly threshold reached for {spacecraft_id}!")
                # Switch to critical bandwidth mode
                self.bandwidth_mode = "critical"
            elif self.anomaly_count[spacecraft_id] > 2:
                self.alert_levels[spacecraft_id] = "WARNING"
                # Switch to low bandwidth mode
                self.bandwidth_mode = "low"
        else:
            # Reset counter if no anomalies
            self.anomaly_count[spacecraft_id] = max(0, self.anomaly_count[spacecraft_id] - 1)
            if self.anomaly_count[spacecraft_id] == 0:
                self.alert_levels[spacecraft_id] = "NOMINAL"
                # Return to normal bandwidth
                self.bandwidth_mode = "normal"
        
        # Add alert level to telemetry
        processed_telemetry.alert_level = self.alert_levels[spacecraft_id]

        # Update last position
        self.last_position[spacecraft_id] = (processed_telemetry.position_x, 
                                            processed_telemetry.position_y, 
                                            processed_telemetry.position_z)

        # Make autonomous decisions - THIS IS THE MAIN DECISION MAKING LOGIC
        commands = self.mission_control.make_decision(processed_telemetry, anomalies)
        
        # Compress the data based on bandwidth mode
        compressed_data = self.compressor.compress_telemetry(processed_telemetry, self.bandwidth_mode)
        print(f"[EDGE] Using {self.bandwidth_mode} bandwidth mode for transmission")
        
        # Simulate packet loss
        if self.comm_simulator.simulate_packet_loss():
            print("[EDGE] Simulated packet loss - data not forwarded to receiver")
            # Still return commands to spacecraft even if receiver connection fails
            return space_telemetry_pb2.TelemetryResponse(
                status="ACK_WITH_COMMANDS" if commands else "ACK",
                message="Telemetry received with " + ("commands" if commands else "no commands"),
                commands=commands
            )
            
        # Forward to Receiver with retry logic for fault tolerance
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with grpc.insecure_channel("localhost:50053") as channel:
                    stub = space_telemetry_pb2_grpc.TelemetryServiceStub(channel)
                    
                    # Simulate transmission delay to receiver
                    transmission_time = self.comm_simulator.simulate_bandwidth_constraint(
                        sys.getsizeof(compressed_data))
                    time.sleep(transmission_time)
                    
                    response = stub.SendTelemetry(processed_telemetry)
                    print(f"[EDGE] Forwarded to receiver | Response: {response}")
                    break
            except Exception as e:
                print(f"[EDGE] Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"[EDGE] Retrying in 1 second...")
                    time.sleep(1)  # Wait before retry
                else:
                    print(f"[EDGE] Failed to send to receiver after {max_retries} attempts")
        
        # Create response with commands for spacecraft
        return space_telemetry_pb2.TelemetryResponse(
            status="ACK_WITH_COMMANDS" if commands else "ACK",
            message="Telemetry processed successfully" + (" with commands" if commands else ""),
            commands=commands
        )
        
    def detect_anomalies(self, telemetry):
        """Detect anomalies in telemetry data"""
        spacecraft_id = telemetry.spacecraft_id
        anomalies = []
        
        # Temperature check
        if telemetry.temperature < self.thresholds['temperature_min'] or telemetry.temperature > self.thresholds['temperature_max']:
            anomalies.append("Temperature out of range")
        
        # Velocity check
        velocity = (telemetry.velocity_x**2 + telemetry.velocity_y**2 + telemetry.velocity_z**2)**0.5
        if velocity > self.thresholds['velocity_max']:
            anomalies.append("Velocity exceeds maximum")
        
        # Position change check
        if spacecraft_id in self.last_position:
            last_pos = self.last_position[spacecraft_id]
            position_change = ((telemetry.position_x - last_pos[0])**2 + 
                            (telemetry.position_y - last_pos[1])**2 + 
                            (telemetry.position_z - last_pos[2])**2)**0.5
            if position_change > self.thresholds['position_change_max'] and sum(last_pos) != 0:
                anomalies.append(f"Abnormal position change: {position_change:.2f}")
        
        # Radiation check if present
        if hasattr(telemetry, 'radiation_level') and telemetry.radiation_level > self.thresholds['radiation_max']:
            anomalies.append(f"Radiation level too high: {telemetry.radiation_level:.2f}")
        
        return anomalies

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    space_telemetry_pb2_grpc.add_TelemetryServiceServicer_to_server(TelemetryProcessor(), server)
    server.add_insecure_port("[::]:50052")
    server.start()
    print(" Edge Processing gRPC Server Running on Port 50052...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()