import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Get log level from env or default to INFO
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def setup_logger(name: str) -> logging.Logger:
    """
    Sets up a professional rotating file logger.
    Limits disk space usage to 5MB per file, keeping 3 backups.
    """
    logger = logging.getLogger(name)

    # If logger already has handlers, return it to avoid duplicate logs
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    # Log format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating)
    log_file = os.path.join(LOGS_DIR, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Create a default system logger
system_logger = setup_logger("system")
