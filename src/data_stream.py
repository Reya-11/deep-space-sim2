import grpc
import time
import random
import math
import numpy as np
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

class Spacecraft:
    def __init__(self, spacecraft_id):
        self.spacecraft_id = spacecraft_id
        
        # Constants
        self.AU = 149597870.7  # km
        
        # Orbital parameters (semi-major axis, eccentricity, inclination, etc.)
        self.semi_major_axis = random.uniform(0.5, 1.2) * self.AU  # km
        self.eccentricity = random.uniform(0.1, 0.3)  # 0=circle, <1=ellipse
        self.inclination = random.uniform(-10, 10) * math.pi / 180  # radians (converts degrees to radians)
        
        # Initial position in orbit
        self.orbit_angle = random.uniform(0, 2 * math.pi)  # Starting position in orbit (radians)
        self.orbit_period = 2 * math.pi * math.sqrt((self.semi_major_axis**3) / (3.98e13))  # Simplified period calculation
        self.orbit_speed = 2 * math.pi / self.orbit_period  # radians per update
        
        # Calculate initial position based on orbital parameters
        self.position_x, self.position_y, self.position_z = self.calculate_position_from_orbit(self.orbit_angle)
        
        # Calculate velocity based on orbital mechanics
        self.velocity_x, self.velocity_y, self.velocity_z = self.calculate_velocity_from_orbit(self.orbit_angle)
        
        # Print initial position
        print(f"[{spacecraft_id}] Initial position: {self.position_x/self.AU:.2f} AU, "
              f"{self.position_y/self.AU:.2f} AU, {self.position_z/self.AU:.2f} AU from Mars")
        
        # Other spacecraft parameters
        self.temperature = random.uniform(-20, 20)
        self.energy_level = 100.0  # Percentage
        self.base_energy_drain = 0.01  # 0.01% drain per update cycle
        self.mode = "NORMAL"  # NORMAL, SAFE, SCIENCE, COMMS, MAINTENANCE
        self.radiation_level = random.uniform(100, 300)
        self.last_maintenance = time.time()
        self.command_queue = []
        
        # Simulation parameters
        self.energy_decay_rate = 0.1  # Energy percentage lost per cycle
        self.orbit_anomaly_chance = 0.02  # 2% chance of orbital anomaly per update
        self.last_anomaly_time = 0

    def calculate_position_from_orbit(self, angle):
        """Calculate 3D position from orbital parameters"""
        # Calculate position in orbital plane
        r = self.semi_major_axis * (1 - self.eccentricity**2) / (1 + self.eccentricity * math.cos(angle))
        
        # Position in orbital plane
        x_orbital = r * math.cos(angle)
        y_orbital = r * math.sin(angle)
        
        # Apply inclination to get 3D position
        x = x_orbital
        y = y_orbital * math.cos(self.inclination)
        z = y_orbital * math.sin(self.inclination)
        
        return x, y, z

    def calculate_velocity_from_orbit(self, angle):
        """Calculate velocity vector tangent to orbit"""
        # Calculate position slightly ahead in orbit
        delta_angle = 0.001
        next_x, next_y, next_z = self.calculate_position_from_orbit(angle + delta_angle)
        
        # Calculate velocity vector (direction of motion)
        vx = (next_x - self.position_x) / delta_angle
        vy = (next_y - self.position_y) / delta_angle
        vz = (next_z - self.position_z) / delta_angle
        
        # Scale to reasonable velocity (a few km/s)
        magnitude = math.sqrt(vx**2 + vy**2 + vz**2)
        scale = random.uniform(3, 7) / magnitude  # Target 3-7 km/s velocity
        
        return vx * scale, vy * scale, vz * scale

    def update_state(self):
        """Update spacecraft state"""
        # First execute any pending commands
        self.execute_commands()
        
        # Store previous position for anomaly detection
        prev_x, prev_y, prev_z = self.position_x, self.position_y, self.position_z
        
        # Regular orbit update
        if random.random() > self.orbit_anomaly_chance:
            # Regular orbital motion
            self.orbit_angle += self.orbit_speed
            if self.orbit_angle > 2 * math.pi:
                self.orbit_angle -= 2 * math.pi  # Keep angle in [0, 2π]
                
            # Calculate new position based on orbit angle
            self.position_x, self.position_y, self.position_z = self.calculate_position_from_orbit(self.orbit_angle)
            
            # Update velocity vector
            self.velocity_x, self.velocity_y, self.velocity_z = self.calculate_velocity_from_orbit(self.orbit_angle)
        else:
            # Generate orbital anomaly (if enough time has passed since last one)
            current_time = time.time()
            if current_time - self.last_anomaly_time > 60:  # Limit anomalies to once per minute
                print(f"[{self.spacecraft_id}] Orbital anomaly occurring!")
                
                # Create a deviation from expected orbit
                deviation_factor = random.uniform(1.05, 1.2)  # 5-20% deviation
                anomaly_type = random.choice(["position", "velocity"])
                
                if anomaly_type == "position":
                    # Position anomaly (unexpected drift)
                    self.position_x += self.velocity_x * deviation_factor
                    self.position_y += self.velocity_y * deviation_factor
                    self.position_z += self.velocity_z * deviation_factor
                else:
                    # Velocity anomaly (unexpected acceleration/deceleration)
                    self.velocity_x *= deviation_factor
                    self.velocity_y *= deviation_factor
                    self.velocity_z *= deviation_factor
                
                self.last_anomaly_time = current_time
            else:
                # Standard update if anomaly is blocked by time limit
                self.orbit_angle += self.orbit_speed
                self.position_x, self.position_y, self.position_z = self.calculate_position_from_orbit(self.orbit_angle)
                self.velocity_x, self.velocity_y, self.velocity_z = self.calculate_velocity_from_orbit(self.orbit_angle)
        
        # Update energy based on power budget
        power_budget = self.calculate_power_budget()
        self.update_energy(power_budget)
        
        # Random temperature fluctuations
        self.temperature += random.uniform(-1, 1)
        
        # Random radiation fluctuations
        self.radiation_level += random.uniform(-10, 10)
        
        # Calculate position change for logging
        delta_pos = math.sqrt(
            (self.position_x - prev_x)**2 + 
            (self.position_y - prev_y)**2 + 
            (self.position_z - prev_z)**2
        )
        
        # Log significant position changes
        if delta_pos > 5000:  # This matches the position_change_max in edge_processing.py
            print(f"[{self.spacecraft_id}] Large position change detected: {delta_pos:.2f} km")

    def execute_commands(self):
        """Execute commands from mission control"""
        if not self.command_queue:
            return
            
        for command in self.command_queue[:]:  # Use a copy of the list to safely modify it
            if command.command_type == "MODE_CHANGE":
                new_mode = command.parameters.get("mode")
                if new_mode:
                    print(f"[{self.spacecraft_id}] Executing command: Change mode to {new_mode}")
                    self.mode = new_mode
            
            elif command.command_type == "TRAJECTORY_ADJUST":
                try:
                    vx_adj = float(command.parameters.get("velocity_x", "0"))
                    vy_adj = float(command.parameters.get("velocity_y", "0"))
                    vz_adj = float(command.parameters.get("velocity_z", "0"))
                    
                    print(f"[{self.spacecraft_id}] Executing command: Trajectory adjustment")
                    self.velocity_x += vx_adj
                    self.velocity_y += vy_adj
                    self.velocity_z += vz_adj
                    
                    # Trajectory adjustments cost energy
                    self.energy_level -= 1.0
                except ValueError:
                    print(f"[{self.spacecraft_id}] Invalid trajectory parameters")
                    
            elif command.command_type == "THERMAL_CONTROL":
                action = command.parameters.get("action")
                if action == "COOLING":
                    print(f"[{self.spacecraft_id}] Executing command: Thermal cooling")
                    self.temperature -= 5
                elif action == "HEATING":
                    print(f"[{self.spacecraft_id}] Executing command: Thermal heating")
                    self.temperature += 5
                    
                # Thermal control costs energy
                self.energy_level -= 0.5
            
            # Remove executed command
            self.command_queue.remove(command)
    
    def add_command(self, command):
        """Add a command to the queue"""
        if command.spacecraft_id == self.spacecraft_id:
            print(f"[{self.spacecraft_id}] Received command: {command.command_type}")
            self.command_queue.append(command)
        else:
            print(f"[{self.spacecraft_id}] Ignoring command for {command.spacecraft_id}")
    
    def calculate_power_budget(self):
        """Calculate power budget for spacecraft systems"""
        # Define power consumption of various systems
        power_consumption = {
            "comms": 25,  # communication system
            "scientific_instruments": 15,  # scientific instruments
            "computer": 10,  # onboard computer
            "navigation": 5,  # navigation systems
            "thermal_control": 10,  # thermal control
            "life_support": 0  # no life support in unmanned missions
        }
        
        # Position of Sun relative to Mars in km
        sun_position_x = -1.5 * self.AU
        sun_position_y = 0
        sun_position_z = 0
        
        # Calculate distance from Sun
        distance_from_sun_km = math.sqrt(
            (self.position_x - sun_position_x)**2 + 
            (self.position_y - sun_position_y)**2 + 
            (self.position_z - sun_position_z)**2
        )
        
        distance_from_sun_au = distance_from_sun_km / self.AU
        
        # Calculate solar input (decreases with square of distance from sun)
        solar_constant = 1361  # W/m² at 1 AU
        
        # Adjust for distance from sun
        solar_input = solar_constant / (distance_from_sun_au**2)
        
        # Solar panel specs
        panel_area = 15  # m²
        panel_efficiency = 0.25  # 25% efficiency
        
        # Calculate solar panel output
        solar_panel_output = solar_input * panel_area * panel_efficiency
        
        # Mode-specific power adjustments
        if self.mode == "SAFE":
            # Safe mode reduces power consumption
            power_consumption["comms"] *= 0.5
            power_consumption["scientific_instruments"] = 0  # Turn off science instruments
        elif self.mode == "SCIENCE":
            # Science mode increases instrument power
            power_consumption["scientific_instruments"] *= 2
        elif self.mode == "COMMS":
            # Comms mode increases communication power
            power_consumption["comms"] *= 2
            power_consumption["scientific_instruments"] *= 0.5  # Reduce science power
        
        # Calculate total consumption
        total_consumption = sum(power_consumption.values())
        
        # Net power (can be negative if consumption exceeds generation)
        net_power = solar_panel_output - total_consumption
        
        return {
            "solar_output": solar_panel_output,
            "consumption": total_consumption,
            "net_power": net_power,
            "details": power_consumption,
            "distance_from_sun_au": distance_from_sun_au
        }
    
    def update_energy(self, power_budget):
        """Update energy levels based on power budget"""
        # Convert power (watts) to energy percentage change
        # Assuming 1000Wh battery
        battery_capacity_wh = 1000  # Watt-hours
        
        # Energy change over 5-second interval (our update cycle)
        interval_hours = 5 / 3600  # 5 seconds in hours
        energy_change_wh = power_budget["net_power"] * interval_hours
        
        # Convert to percentage
        energy_change_percent = (energy_change_wh / battery_capacity_wh) * 100
        
        # Apply slow base drain regardless of power budget (life support, background systems)
        energy_change_percent -= self.base_energy_drain
        
        # Update energy level
        self.energy_level += energy_change_percent
        
        # Clamp to valid range
        self.energy_level = max(0, min(100, self.energy_level))
        
        # Print energy status if it's low or charging
        if self.energy_level < 30 or power_budget["net_power"] < 0:
            print(f"[{self.spacecraft_id}] Energy: {self.energy_level:.1f}%, " + 
                  f"Power balance: {power_budget['net_power']:.1f}W, Base drain: {self.base_energy_drain:.3f}%")
    
    def generate_telemetry(self):
        """Generate telemetry data"""
        # Update state before generating telemetry
        self.update_state()
        
        return space_telemetry_pb2.TelemetryData(
            spacecraft_id=self.spacecraft_id,
            timestamp=time.time(),
            position_x=self.position_x,
            position_y=self.position_y,
            position_z=self.position_z,
            velocity_x=self.velocity_x,
            velocity_y=self.velocity_y,
            velocity_z=self.velocity_z,
            temperature=self.temperature,
            radiation_level=self.radiation_level,
            energy_level=self.energy_level,
            mode=self.mode
        )

    def send_telemetry(self):
        """Send telemetry data to the edge processing service"""
        try:
            # Create telemetry data message
            telemetry = space_telemetry_pb2.TelemetryData(
                spacecraft_id=self.spacecraft_id,
                timestamp=time.time(),
                position_x=self.position_x,
                position_y=self.position_y,
                position_z=self.position_z,
                velocity_x=self.velocity_x,
                velocity_y=self.velocity_y,
                velocity_z=self.velocity_z,
                temperature=self.temperature,
                radiation_level=self.radiation_level,
                energy_level=self.energy_level,
                mode=self.mode,
                orbit_angle=self.orbit_angle
            )
            
            # Send to edge processing service
            response = self.telemetry_stub.SendTelemetry(telemetry)
            print(f"[{self.spacecraft_id}] Telemetry sent. Response: {response.message}")
            
        except Exception as e:
            print(f"[{self.spacecraft_id}] Error sending telemetry: {e}")

def main():
    spacecraft = Spacecraft("Voyager-1")
    connection_attempts = 0
    max_connection_attempts = 10
    
    while connection_attempts < max_connection_attempts:
        try:
            channel = grpc.insecure_channel("localhost:50052")
            stub = space_telemetry_pb2_grpc.TelemetryServiceStub(channel)
            
            # If we get here, connection succeeded
            print("[DATA] Successfully connected to Edge Processing server")
            spacecraft.telemetry_stub = stub
            break
        except Exception as e:
            connection_attempts += 1
            print(f"[DATA] Connection attempt {connection_attempts}/{max_connection_attempts} failed: {e}")
            time.sleep(2)  # Wait before retry
            
    if connection_attempts >= max_connection_attempts:
        print("[DATA] Failed to connect to Edge Processing server. Exiting.")
        return

    while True:
        try:
            # Generate telemetry data
            telemetry_data = spacecraft.generate_telemetry()
            
            # Send telemetry and receive commands
            response = stub.SendTelemetry(telemetry_data)
            
            print(f"[DATA] Sent telemetry: {spacecraft.mode} mode, Energy: {spacecraft.energy_level:.1f}%, " +
                  f"Temp: {spacecraft.temperature:.1f}°C | Response: {response.status}")
            
            # Process commands from mission control
            if response.commands:
                print(f"[DATA] Received {len(response.commands)} command(s) from Mission Control")
                for command in response.commands:
                    spacecraft.add_command(command)
                    
            time.sleep(5)  # Send data every 5 seconds
            
        except grpc.RpcError as e:
            print(f"[DATA] gRPC Error: {e.code()} - {e.details()}")
            time.sleep(10)  # Wait longer on error

if __name__ == "__main__":
    main()