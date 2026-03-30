import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Log dizini
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"ed_quant_{datetime.now().strftime('%Y-%m')}.log")

# Format
formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | [%(module)s] %(message)s')

# Rotating File Handler: Max 5MB, keep 3 backups
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(formatter)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Logger Initialization
logger = logging.getLogger("ED_Quant")
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logger.setLevel(log_level)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_logger(module_name: str) -> logging.Logger:
    """Returns a logger instance specifically named for the module calling it."""
    return logger.getChild(module_name)
