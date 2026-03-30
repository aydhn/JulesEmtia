import logging
from logging.handlers import RotatingFileHandler
import os

os.makedirs('logs', exist_ok=True)

logger = logging.getLogger("QuantEngine")
logger.setLevel(logging.DEBUG)

# Rotating file handler (Max 5MB, 3 backups)
fh = RotatingFileHandler("logs/quant_engine.log", maxBytes=5*1024*1024, backupCount=3)
fh.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

def get_logger():
    return logger
