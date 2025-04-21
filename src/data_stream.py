import time
import random
import math
import grpc
import socket
import json
import threading
from datetime import datetime
import space_telemetry_pb2
import space_telemetry_pb2_grpc

# Constants for realistic space values
AU = 149597870.7  # 1 Astronomical Unit in km
SUN_MASS = 1.989e30  # Mass of Sun in kg
G = 6.67430e-11  # Gravitational constant
EARTH_ORBIT_VELOCITY = 29.78  # km/s
MARS_ORBIT_VELOCITY = 24.13    # km/s
JUPITER_ORBIT_VELOCITY = 13.07  # km/s
SATURN_ORBIT_VELOCITY = 9.69    # km/s
TYPICAL_SPACECRAFT_TEMP_RANGE = (-150, 100)  # Celsius

class SpacecraftSimulator:
    def __init__(self, spacecraft_id, mission_type="earth_orbit"):
        self.spacecraft_id = spacecraft_id
        self.paused = False
        self.anomaly_mode = False
        self.sos_mode = False
        self.anomaly_count = 0
        self.anomaly_descriptions = ""
        self.anomaly_severity = "low"
        self.decisions_made = 0
        self.decisions_descriptions = []
        self.sos_reason = ""
        self.sequence_num = 0
        self.signal_quality = 100.0

        # Internal spacecraft systems
        self.temperature = random.uniform(-20, 30)  # Starting temperature
        self.battery_level = 100.0
        self.solar_panel_output = 1.0
        self.timestamp = time.time()
        self.last_major_update = time.time()  # Add this line
        
        # Set orbital parameters based on mission type
        self.mission_type = mission_type
        self.setup_mission_parameters()
        
    def setup_mission_parameters(self):
        """Set up realistic orbital parameters based on mission type"""
        # Create variation based on spacecraft_id hash
        id_hash = sum(ord(c) for c in self.spacecraft_id)
        
        # Common parameters
        self.epoch = time.time()
        self.reference_frame = "heliocentric"  # Sun-centered
        
        if self.mission_type == "earth_orbit":
            # Earth orbit parameters (LEO to GEO)
            self.semi_major_axis = 6771 + (id_hash % 36000)  # km (altitude + Earth radius)
            self.eccentricity = 0.0001 + (id_hash % 20) / 1000
            self.inclination = (id_hash % 90) * math.pi / 180  # 0-90 degrees in radians
            self.mean_motion = math.sqrt(G * SUN_MASS / (self.semi_major_axis * 1000)**3)  # rad/s
            self.distance_factor = 1.0  # Signal delay factor
            
        elif self.mission_type == "mars_mission":
            # Mars mission parameters
            self.semi_major_axis = 1.5 * AU  # Mars average distance
            self.eccentricity = 0.0934 + (id_hash % 10) / 100
            self.inclination = 0.032 * math.pi + (id_hash % 10) * 0.01
            self.mean_motion = math.sqrt(G * SUN_MASS / (self.semi_major_axis * 1000)**3)
            self.distance_factor = 1.5  # Greater signal delay
            
        elif self.mission_type == "asteroid_belt":
            # Asteroid belt mission parameters
            self.semi_major_axis = 2.7 * AU + (id_hash % 10) * 0.1 * AU
            self.eccentricity = 0.1 + (id_hash % 20) / 100
            self.inclination = (id_hash % 30) * math.pi / 180
            self.mean_motion = math.sqrt(G * SUN_MASS / (self.semi_major_axis * 1000)**3)
            self.distance_factor = 2.7  # Even greater delay
            
        elif self.mission_type == "outer_planets":
            # Outer planet mission parameters
            self.semi_major_axis = 5.2 * AU + (id_hash % 30) * 0.1 * AU  # Jupiter and beyond
            self.eccentricity = 0.05 + (id_hash % 10) / 100
            self.inclination = (id_hash % 10) * math.pi / 180
            self.mean_motion = math.sqrt(G * SUN_MASS / (self.semi_major_axis * 1000)**3)
            self.distance_factor = 5.2  # Major signal delay
            
        # Common orbital elements
        self.raan = (id_hash % 360) * math.pi / 180
        self.arg_periapsis = ((id_hash * 7) % 360) * math.pi / 180
        self.mean_anomaly = ((id_hash * 13) % 360) * math.pi / 180
        
        # Initialize position and velocity
        self.update()
        
    def calculate_orbital_position(self):
        """Calculate spacecraft position using Keplerian orbital elements"""
        # Time since epoch
        time_since_epoch = time.time() - self.epoch
        
        # Update mean anomaly based on elapsed time
        mean_anomaly = (self.mean_anomaly + self.mean_motion * time_since_epoch) % (2 * math.pi)
        
        # Solve Kepler's equation for eccentric anomaly using Newton-Raphson method
        eccentric_anomaly = mean_anomaly  # Initial guess
        for i in range(10):  # Fixed: Using range(10) instead of (10)
            delta_e = (eccentric_anomaly - self.eccentricity * math.sin(eccentric_anomaly) - mean_anomaly) / \
                     (1.0 - self.eccentricity * math.cos(eccentric_anomaly))
            eccentric_anomaly -= delta_e
            if abs(delta_e) < 1e-8:
                break
                
        # Calculate true anomaly
        cos_e = math.cos(eccentric_anomaly)
        sin_e = math.sin(eccentric_anomaly)
        fac = math.sqrt((1.0 + self.eccentricity) / (1.0 - self.eccentricity))
        true_anomaly = 2.0 * math.atan2(fac * sin_e, cos_e + self.eccentricity)
        
        # Calculate distance from central body
        distance = self.semi_major_axis * (1.0 - self.eccentricity * cos_e)
        
        # Position in orbital plane
        pos_x = distance * math.cos(true_anomaly)
        pos_y = distance * math.sin(true_anomaly)
        pos_z = 0.0
        
        # Rotation matrices to transform to reference frame
        # First, rotation from periapsis by argument of periapsis
        xp = pos_x * math.cos(self.arg_periapsis) - pos_y * math.sin(self.arg_periapsis)
        yp = pos_x * math.sin(self.arg_periapsis) + pos_y * math.cos(self.arg_periapsis)
        zp = pos_z
        
        # Then, rotation from orbital plane by inclination
        xq = xp
        yq = yp * math.cos(self.inclination)
        zq = yp * math.sin(self.inclination)
        
        # Finally, rotation around reference z-axis by RAAN
        x = xq * math.cos(self.raan) - yq * math.sin(self.raan)
        y = xq * math.sin(self.raan) + yq * math.cos(self.raan)
        z = zq
        
        # Calculate velocity from orbital elements
        # This is a simplified velocity calculation
        velocity_factor = math.sqrt(G * SUN_MASS / distance)
        
        if self.mission_type == "earth_orbit":
            speed = EARTH_ORBIT_VELOCITY
        elif self.mission_type == "mars_mission":
            speed = MARS_ORBIT_VELOCITY
        elif self.mission_type == "asteroid_belt":
            speed = MARS_ORBIT_VELOCITY * 0.7
        else:
            speed = JUPITER_ORBIT_VELOCITY
            
        # Direction is perpendicular to position vector in orbital plane
        vel_direction = true_anomaly + math.pi/2
        vx = -speed * math.sin(vel_direction)
        vy = speed * math.cos(vel_direction)
        vz = 0.0
        
        # Return position and velocity vectors
        position = [x, y, z]
        velocity = [vx, vy, vz]
        return position, velocity, distance
    
    def update(self):
        """Update spacecraft state"""
        self.timestamp = time.time()
        self.sequence_num += 1
        
        # Update position and velocity based on orbital mechanics
        position, velocity, distance = self.calculate_orbital_position()
        self.position_x, self.position_y, self.position_z = position
        self.velocity_x, self.velocity_y, self.velocity_z = velocity
        
        # Calculate signal quality and delay based on distance
        # Signal quality decreases with distance and random fluctuations
        signal_delay = (distance / 299792.458) * self.distance_factor  # Speed of light in km/s
        base_signal_quality = 100 - (30 * min(distance / (2 * AU), 1.0))  # Decrease with distance
        fluctuation = random.uniform(-5, 5)  # Add small random fluctuations
        self.signal_quality = max(0, min(100, base_signal_quality + fluctuation))
        
        # Update temperature based on distance from sun and spacecraft operations
        # Closer to sun = hotter, further = colder
        distance_from_sun = math.sqrt(self.position_x**2 + self.position_y**2 + self.position_z**2)
        sun_factor = 100 / (distance_from_sun / AU)**2  # Inverse square law
        
        # Temperature fluctuates based on operations and sun exposure
        if time.time() - self.last_major_update > 30:
            self.temperature += random.uniform(-5, 5)
            self.last_major_update = time.time()
        
        # Gradual pull toward equilibrium temperature based on distance from sun
        equilibrium_temp = 80 - (distance_from_sun / AU) * 40
        self.temperature = 0.95 * self.temperature + 0.05 * equilibrium_temp
        
        # Ensure temperature stays in realistic range
        self.temperature = max(TYPICAL_SPACECRAFT_TEMP_RANGE[0], 
                              min(TYPICAL_SPACECRAFT_TEMP_RANGE[1], self.temperature))
        
        # Generate anomalies
        self.check_for_anomalies()
        
        # Update battery and solar panel status
        self.update_power_systems(sun_factor)
        
    def update_power_systems(self, sun_factor):
        """Update power systems based on sun exposure"""
        # Solar panel output depends on orientation and distance from sun
        self.solar_panel_output = 0.8 + 0.2 * sun_factor / 100 + random.uniform(-0.05, 0.05)
        self.solar_panel_output = max(0.1, min(1.0, self.solar_panel_output))
        
        # Battery drains or charges
        if self.solar_panel_output > 0.6:
            self.battery_level = min(100, self.battery_level + 0.2)
        else:
            self.battery_level = max(0, self.battery_level - 0.1)
            
    def check_for_anomalies(self):
        """Check for and generate anomalies"""
        self.anomaly_count = 0
        self.anomaly_descriptions = ""
        self.anomaly_severity = "low"
        self.decisions_made = 0
        self.decisions_descriptions = []
        
        if self.anomaly_mode or random.random() < 0.02:  # 2% chance of anomaly per update
            anomaly_types = [
                "Thermal regulation fluctuation",
                "Communication subsystem interference",
                "Power system irregularity",
                "Attitude control deviation",
                "Sensor calibration drift",
                "Radiation event detected",
                "Navigation system variance",
                "Propulsion system pressure anomaly",
                "Minor data corruption",
                "Memory management warning"
            ]
            
            self.anomaly_count = random.randint(1, 3)
            anomalies = random.sample(anomaly_types, self.anomaly_count)
            self.anomaly_descriptions = ";".join(anomalies)
            self.anomaly_severity = random.choice(["low", "medium", "high"])
            
            # For serious anomalies, generate autonomous decisions
            if self.anomaly_severity in ["medium", "high"]:
                decision_types = [
                    "Initiated power conservation mode",
                    "Performed sensor recalibration",
                    "Switched to backup communication array",
                    "Adjusted thermal control parameters",
                    "Realigned attitude control",
                    "Performed memory defragmentation",
                    "Optimized communication frequency",
                    "Activated radiation protection protocols"
                ]
                
                self.decisions_made = random.randint(1, 2)
                self.decisions_descriptions = random.sample(decision_types, self.decisions_made)
            
            # For critical anomalies, set SOS mode
            if self.anomaly_severity == "high" and random.random() < 0.3:
                self.sos_mode = True
                self.sos_reason = f"Critical system failure: {self.anomaly_descriptions}"
        
    def get_telemetry(self):
        """Generate telemetry data message"""
        telemetry = space_telemetry_pb2.TelemetryData(
            spacecraft_id=self.spacecraft_id,
            timestamp=self.timestamp,
            position_x=self.position_x,
            position_y=self.position_y,
            position_z=self.position_z,
            velocity_x=self.velocity_x,
            velocity_y=self.velocity_y,
            velocity_z=self.velocity_z,
            temperature=self.temperature,
            anomaly_count=self.anomaly_count,
            anomaly_severity=self.anomaly_severity,
            anomaly_descriptions=self.anomaly_descriptions,
            decisions_made=self.decisions_made,
            decisions_descriptions=";".join(self.decisions_descriptions),
            signal_quality=self.signal_quality,
            sequence_num=self.sequence_num
        )
        
        if self.sos_mode:
            telemetry.sos_required = True
            telemetry.sos_reason = self.sos_reason
            
        return telemetry
    
    def toggle_pause(self):
        """Toggle the paused state"""
        self.paused = not self.paused
        return self.paused
        
    def toggle_anomaly(self):
        """Toggle anomaly simulation mode"""
        self.anomaly_mode = not self.anomaly_mode
        return self.anomaly_mode
        
    def send_sos(self, reason):
        """Set SOS mode with specific reason"""
        self.sos_mode = True
        self.sos_reason = reason
        return True

def control_server(spacecraft_list):
    """Simple control socket server to allow controlling the simulation"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind(('localhost', 50055))
        server_socket.listen(5)
        print("[CONTROL] Server listening on port 50051")
        
        while True:
            client, addr = server_socket.accept()
            try:
                data = client.recv(1024)
                if not data:
                    continue
                    
                message = json.loads(data.decode('utf-8'))
                response = {"status": "error", "message": "Invalid command"}
                
                # Process control commands
                if message.get("command") == "list":
                    response = {
                        "status": "success", 
                        "spacecraft": [s.spacecraft_id for s in spacecraft_list]
                    }
                elif message.get("command") == "pause":
                    spacecraft_id = message.get("spacecraft_id")
                    for s in spacecraft_list:
                        if s.spacecraft_id == spacecraft_id:
                            paused = s.toggle_pause()
                            response = {
                                "status": "success", 
                                "spacecraft_id": spacecraft_id,
                                "paused": paused
                            }
                            break
                elif message.get("command") == "anomaly":
                    spacecraft_id = message.get("spacecraft_id")
                    for s in spacecraft_list:
                        if s.spacecraft_id == spacecraft_id:
                            anomaly = s.toggle_anomaly()
                            response = {
                                "status": "success", 
                                "spacecraft_id": spacecraft_id,
                                "anomaly_mode": anomaly
                            }
                            break
                elif message.get("command") == "sos":
                    spacecraft_id = message.get("spacecraft_id")
                    reason = message.get("reason", "Manual SOS triggered")
                    for s in spacecraft_list:
                        if s.spacecraft_id == spacecraft_id:
                            s.send_sos(reason)
                            response = {
                                "status": "success", 
                                "spacecraft_id": spacecraft_id,
                                "sos_triggered": True
                            }
                            break
                            
                client.send(json.dumps(response).encode('utf-8'))
            except Exception as e:
                print(f"[CONTROL] Error: {e}")
            finally:
                client.close()
    except Exception as e:
        print(f"[CONTROL] Server error: {e}")
    finally:
        server_socket.close()

def run():
    """Main function to run spacecraft simulators"""
    # Create spacecraft with realistic missions
    spacecraft_list = [
        SpacecraftSimulator("DeepSpace-1", mission_type="earth_orbit"),
        SpacecraftSimulator("Voyager-4", mission_type="mars_mission"),
        SpacecraftSimulator("Pioneer-12", mission_type="asteroid_belt"),
        SpacecraftSimulator("NewHorizons-2", mission_type="outer_planets")
    ]
    print(f"[DATA STREAM] Simulating {len(spacecraft_list)} spacecraft...")

    # Start control server in background thread
    threading.Thread(target=control_server, args=(spacecraft_list,), daemon=True).start()

    # Connect to edge processing
    stub = space_telemetry_pb2_grpc.TelemetryServiceStub(grpc.insecure_channel("localhost:50052"))

    try:
        while True:
            for sc in spacecraft_list:
                if sc.paused:
                    continue
                    
                sc.update()
                telemetry = sc.get_telemetry()
                
                try:
                    stub.SendTelemetry(telemetry)
                    print(f"[{telemetry.spacecraft_id}] Telemetry sent: "
                          f"Pos({telemetry.position_x/AU:.3f}, {telemetry.position_y/AU:.3f}, {telemetry.position_z/AU:.3f}) AU, "
                          f"Vel({telemetry.velocity_x:.2f}, {telemetry.velocity_y:.2f}, {telemetry.velocity_z:.2f}) km/s, "
                          f"Temp: {telemetry.temperature:.1f}°C, "
                          f"Signal: {telemetry.signal_quality:.1f}%")
                          
                except grpc.RpcError as e:
                    print(f"[{telemetry.spacecraft_id}] ❌ gRPC error: {e}")
                    
                time.sleep(0.2)  # Slight delay between spacecraft updates
                
            time.sleep(0.8)  # Overall update cycle delay
            
    except KeyboardInterrupt:
        print("[DATA STREAM] Shutdown requested. Exiting.")

if __name__ == "__main__":
    run()
