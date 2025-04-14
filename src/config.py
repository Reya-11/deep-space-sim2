"""
Configuration file for deep space simulation.
Contains spacecraft parameters and simulation constants.
"""
from typing import Dict, Any

# Astronomical constants
AU: float = 149597870.7  # Astronomical Unit in km
MARS_RADIUS: float = 3389.5  # Mars radius in km
EARTH_RADIUS: float = 6371.0  # Earth radius in km
SUN_RADIUS: float = 696340.0  # Sun radius in km
SPEED_OF_LIGHT: float = 299792.458  # Speed of light in km/s

# Spacecraft configurations
SPACECRAFT_CONFIG: Dict[str, Dict[str, Any]] = {
    "Voyager-1": {
        "panel_area": 15.0,  # m²
        "panel_efficiency": 0.25,  # 25% efficiency
        "battery_capacity_wh": 1000.0,  # Watt-hours
        "orbit_anomaly_chance": 0.02,  # 2% chance of orbital anomaly
        "base_energy_drain": 0.01,  # 0.01% drain per update cycle
        "comms_frequency_mhz": 8400.0,  # X-band frequency in MHz
        "antenna_gain_db": 42.0,  # High gain antenna in dB
        "transmitter_power_w": 20.0,  # Transmitter power in Watts
        "radiation_sensitivity": 1.0,  # Multiplier for radiation effects
        "thermal_limits": {
            "min_operational": -45.0,  # Minimum operational temperature in Celsius
            "max_operational": 50.0,   # Maximum operational temperature in Celsius
            "critical_low": -70.0,     # Critical low temperature in Celsius
            "critical_high": 85.0      # Critical high temperature in Celsius
        }
    },
    # Add more spacecraft configurations as needed
}

# Celestial body positions relative to Mars (in km)
CELESTIAL_BODIES = {
    "Mars": {
        "position": [0.0, 0.0, 0.0],
        "radius": MARS_RADIUS,
        "color": "#c1440e",
        "glow": "#ff5722"
    },
    "Earth": {
        "position": [-0.6 * AU, -1.2 * AU, 0.0],
        "radius": EARTH_RADIUS,
        "color": "#0077be", 
        "glow": "#29b6f6"
    },
    "Sun": {
        "position": [-1.5 * AU, 0.0, 0.0],
        "radius": SUN_RADIUS,
        "color": "#ffcc00",
        "glow": "#ffeb3b"
    }
}

# Simulation parameters
SIMULATION_CONFIG = {
    "update_interval_sec": 5.0,  # Simulation update interval
    "max_connection_attempts": 10,  # Maximum connection attempts to server
    "connection_retry_interval_sec": 2.0,  # Seconds to wait between connection attempts
    "solar_constant": 1361.0,  # Solar energy at 1 AU in W/m²
    "communication_delay_enabled": True,  # Enable realistic light-speed communication delay
    "random_seed": 42  # Seed for random number generation
}

# Power consumption of spacecraft systems in Watts
POWER_CONSUMPTION = {
    "comms": 25.0,           # Communication system
    "scientific_instruments": 15.0,  # Scientific instruments
    "computer": 10.0,        # Onboard computer
    "navigation": 5.0,       # Navigation systems
    "thermal_control": 10.0, # Thermal control
    "life_support": 0.0      # No life support in unmanned missions
}

# Environmental events configuration
ENVIRONMENTAL_EVENTS = {
    "solar_flare": {
        "probability": 0.001,  # 0.1% chance per update
        "radiation_increase": 300.0,  # Increase in radiation level
        "duration_updates": 12,  # Duration in number of updates
    },
    "micrometeorite": {
        "probability": 0.002,  # 0.2% chance per update
        "damage_range": [0.1, 1.0],  # Range of potential damage to energy systems
    }
}

# Log configuration
LOG_CONFIG = {
    "level": "INFO",  # Logging level
    "format": "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "file": "spacecraft.log"  # Log file name
}