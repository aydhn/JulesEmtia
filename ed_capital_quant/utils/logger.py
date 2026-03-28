import logging
from logging.handlers import RotatingFileHandler
import os
from core.config import LOG_DIR

def setup_logger():
    logger = logging.getLogger("ED_Quant")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(f"{LOG_DIR}/quant.log", maxBytes=5*1024*1024, backupCount=3)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

log = setup_logger()
