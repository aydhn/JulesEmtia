import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger():
    logger = logging.getLogger("ED_Quant")
    logger.setLevel(logging.INFO)

    # Optional: ensure logs directory exists
    os.makedirs("logs", exist_ok=True)

    handler = RotatingFileHandler("logs/ed_quant.log", maxBytes=5*1024*1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(handler)

    return logger

log = setup_logger()
