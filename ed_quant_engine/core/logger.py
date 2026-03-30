import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger() -> logging.Logger:
    """Sets up and returns a professional logger with RotatingFileHandler."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    log_file = os.path.join(log_dir, 'quant_engine.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3) # 5MB limit
    file_handler.setFormatter(log_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)

    logger = logging.getLogger("ED_Quant_Engine")

    # Singleton pattern to prevent duplicate logs
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
