import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Build logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Define formatter
FORMATTER = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def setup_logger(name: str) -> logging.Logger:
    """
    Creates and returns a logger with rotating file handler and console handler.
    Follows Quant standards for debugging and critical alerting.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent duplicate logs if initialized multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    logger.addHandler(console_handler)

    # File Handler (Rotating: Max 5MB per file, keep 3 backups)
    log_file = os.path.join(LOGS_DIR, f"quant_engine_{datetime.now().strftime('%Y-%m')}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(FORMATTER)
    logger.addHandler(file_handler)

    return logger

# Global logger instance
logger = setup_logger("EDCapital")
