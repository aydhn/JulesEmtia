import logging
from logging.handlers import RotatingFileHandler
import os

os.makedirs('logs', exist_ok=True)
logger = logging.getLogger("EDQuant")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler('logs/quant_engine.log', maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)