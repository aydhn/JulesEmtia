import logging
from logging.handlers import RotatingFileHandler
import os

from ed_quant_engine.config import LOGS_DIR

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # Console Handler
        c_handler = logging.StreamHandler()
        c_handler.setLevel(logging.INFO)

        # File Handler (rotating up to 5MB, keep 3 backups)
        f_handler = RotatingFileHandler(
            os.path.join(LOGS_DIR, f"{name}.log"),
            maxBytes=5*1024*1024,
            backupCount=3
        )
        f_handler.setLevel(logging.DEBUG)

        # Formatters
        c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    return logger

log = setup_logger('quant_engine')
