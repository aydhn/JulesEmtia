import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "quant_bot.log")
LOG_LEVEL_ENV = os.getenv("LOG_LEVEL", "INFO")

def setup_logger(name: str) -> logging.Logger:
    """Configures a professional rotating file logger suitable for long-running daemons."""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL_ENV)

    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Rotating File Handler (Max 5MB per file, keep 3 backups)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setFormatter(formatter)

        # Stream Handler (Console for Docker logs / tail)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger
