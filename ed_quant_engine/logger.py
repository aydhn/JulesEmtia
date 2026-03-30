import logging
from logging.handlers import RotatingFileHandler
import os

from config import LOG_FILE, LOG_LEVEL

def setup_logger(name="ed_quant", log_file=LOG_FILE, level=LOG_LEVEL):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if not logger.handlers:
        # Rotating File Handler (5 MB max, 3 backups)
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

log = setup_logger()
