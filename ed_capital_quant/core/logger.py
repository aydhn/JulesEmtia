"""
ED Capital Quant Engine - Logging Module
Professional logging system with rotating file handlers and Telegram alerts.
"""
import logging
from logging.handlers import RotatingFileHandler
import os
from .config import LOG_DIR
from .notifier import notify_admin

class QuantLogger:
    def __init__(self, name="ED_Capital_Quant"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)

        # File Handler (Rotating)
        log_file = os.path.join(LOG_DIR, "quant_engine.log")
        fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        self.logger.addHandler(ch)
        self.logger.addHandler(fh)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        """Kritik hatalarda logla ve Telegram'dan anında bildir."""
        self.logger.critical(msg)
        try:
            notify_admin(f"🚨 CRITICAL SYSTEM ERROR: {msg}")
        except Exception as e:
            self.logger.error(f"Failed to send critical Telegram alert: {e}")

logger = QuantLogger()
