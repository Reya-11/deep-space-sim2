"""
Logger module for the spacecraft simulation.
Provides consistent logging across all components.
"""
import logging
import sys
from typing import Optional
from datetime import datetime
from pathlib import Path
from src.config import LOG_CONFIG

def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up and return a logger with the specified name.
    
    Args:
        name: Name for the logger
        log_file: Optional path to a log file
        
    Returns:
        logger: Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_CONFIG["level"]))
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=LOG_CONFIG["format"], 
        datefmt=LOG_CONFIG["date_format"]
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if specified
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file).parent
        log_path.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create main simulation logger
sim_logger = setup_logger("sim", "logs/spacecraft.log")

# Specialized loggers
telemetry_logger = setup_logger("telemetry", "logs/telemetry.log")
comms_logger = setup_logger("comms", "logs/communications.log")
anomaly_logger = setup_logger("anomaly", "logs/anomalies.log")