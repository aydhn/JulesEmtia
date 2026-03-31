import logging
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Format for the logs
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set up the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# File handler with rotation (max 5MB, keep 3 backups)
file_handler = RotatingFileHandler(
    "logs/ed_quant.log", maxBytes=5 * 1024 * 1024, backupCount=3
)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger for the given name.
    """
    return logging.getLogger(name)
