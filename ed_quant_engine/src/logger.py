import logging
import os
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("ED_Quant_Engine")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# File handler with rotation (max 5MB, keep 3 backups)
fh = RotatingFileHandler('logs/quant_engine.log', maxBytes=5*1024*1024, backupCount=3)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

def get_logger():
    return logger
