import logging
import os
from logging.handlers import RotatingFileHandler

# Import notifier later or pass it dynamically to avoid circular dependency
# import ed_quant_engine.notifications.notifier as notifier

def setup_logger(name="QuantEngine", log_file="logs/quant_engine.log", level=logging.INFO):
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        # File Handler (5MB max, 3 backups)
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        file_handler.setLevel(level)

        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()

def log_critical(msg: str):
    logger.critical(msg)
    # We will trigger telegram via a global handler or direct import if needed
