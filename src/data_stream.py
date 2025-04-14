import grpc
import time
import random
import math
import numpy as np
import space_telemetry_pb2 as space_telemetry_pb2, space_telemetry_pb2_grpc as space_telemetry_pb2_grpc

class Spacecraft:
    def __init__(self, spacecraft_id):
        self.spacecraft_id = spacecraft_id
        
        # Initial position in meters
        # Set the spacecraft far into deep space (1-5 light-years away)
        light_year = 9.461e15  # meters
        
        # Random direction from Earth
        direction = np.random.rand(3)
        direction = direction / np.linalg.norm(direction)  # Normalize to unit vector
        
        # Random distance between 1-5 light-years
        distance = np.random.uniform(1, 5) * light_year
        
        # Set initial position
        self.position_x = direction[0] * distance
        self.position_y = direction[1] * distance
        self.position_z = direction[2] * distance
        
        # Very small velocity (realistic for deep space)
        self.velocity_x = np.random.uniform(-1000, 1000)  # m/s
        self.velocity_y = np.random.uniform(-1000, 1000)  # m/s
        self.velocity_z = np.random.uniform(-1000, 1000)  # m/s
        
        self.temperature = random.uniform(-20, 20)
        self.energy_level = 100.0  # Percentage
        self.base_energy_drain = 0.01  # 0.01% drain per update cycle
        self.mode = "NORMAL"  # NORMAL, SAFE, SCIENCE, COMMS, MAINTENANCE
        self.radiation_level = random.uniform(100, 300)
        self.last_maintenance = time.time()
        self.command_queue = []
        
        # Simulation parameters
        self.energy_decay_rate = 0.1  # Energy percentage lost per cycle
        
    def update_state(self):
        """Update spacecraft state"""
        # First execute any pending commands
        self.execute_commands()
        
        # Update position based on velocity
        self.position_x += self.velocity_x
        self.position_y += self.velocity_y
        self.position_z += self.velocity_z
        
        # Update energy based on power budget
        power_budget = self.calculate_power_budget()
        self.update_energy(power_budget)
        
        # Random temperature fluctuations
        self.temperature += random.uniform(-1, 1)
        
        # Random radiation fluctuations
        self.radiation_level += random.uniform(-10, 10)
        
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
        """Calculate current power budget"""
        # Base power consumption
        power_budget = {
            "systems": {
                "computer": 5.0,  # Watts
                "comms": 15.0,    # Watts
                "sensors": 8.0,   # Watts
                "propulsion": 0.0,  # Watts, only used during maneuvers
                "science": 0.0,    # Watts, only used during science operations
                "heaters": 0.0     # Watts, variable based on temperature
            },
            "total_consumption": 0.0,
            "solar_input": 0.0,
            "net_power": 0.0
        }
        
        # Adjust based on mode
        if self.mode == "SAFE":
            power_budget["systems"]["comms"] = 5.0  # Reduced comms
            power_budget["systems"]["sensors"] = 3.0  # Minimal sensors
        elif self.mode == "SCIENCE":
            power_budget["systems"]["science"] = 25.0  # Science instruments
        elif self.mode == "COMMS":
            power_budget["systems"]["comms"] = 30.0  # High-power transmission
            
        # Temperature-dependent heater power
        if self.temperature < -10:
            heater_power = 20.0
            power_budget["systems"]["heaters"] = heater_power
        elif self.temperature < 0:
            heater_power = 10.0
            power_budget["systems"]["heaters"] = heater_power
            
        # Calculate total consumption
        total = sum(power_budget["systems"].values())
        power_budget["total_consumption"] = total
        
        # Calculate solar input (decreases with square of distance from sun)
        # Assume distance in AU is roughly position_z/100 for simplicity
        distance_from_sun_au = abs(self.position_z/100) + 1  # Prevent division by zero
        solar_constant = 1361  # W/m² at Earth
        solar_panel_area = 10  # m²
        solar_panel_efficiency = 0.3
        solar_input = solar_constant * solar_panel_area * solar_panel_efficiency / (distance_from_sun_au ** 2)
        power_budget["solar_input"] = solar_input
        
        # Net power (positive means charging, negative means discharging)
        power_budget["net_power"] = solar_input - total
        
        return power_budget
    
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