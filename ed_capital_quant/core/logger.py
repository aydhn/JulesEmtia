import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class QuantLogger:
    def __init__(self, name: str = "ED_Capital"):
        self.logger = logging.getLogger(name)
        if not self.logger.hasHandlers():
            self.logger.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

            # Rotating File Handler (Max 5MB, 3 Backups)
            file_handler = RotatingFileHandler(
                os.path.join(LOG_DIR, "quant_engine.log"),
                maxBytes=5*1024*1024,
                backupCount=3
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)

            # Console Handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger

logger = QuantLogger().get_logger()
