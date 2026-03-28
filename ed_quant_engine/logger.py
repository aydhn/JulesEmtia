import logging
from logging.handlers import RotatingFileHandler
import os

from config import LOG_PATH

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logger = logging.getLogger("EDCapitalQuant")
logger.setLevel(logging.INFO)

# Rotating file handler: 5MB max, 3 backups
file_handler = RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console output for testing
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def get_logger():
    return logger
