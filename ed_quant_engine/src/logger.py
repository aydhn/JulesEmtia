import logging
import os
from logging.handlers import RotatingFileHandler
import sys

# Konfigürasyonu buradan alıyoruz (dosya yolları vs)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import LOG_DIR

# Log dizinini oluştur
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "ed_quant_engine.log")

# Logger Yapılandırması
logger = logging.getLogger("EDQuantEngine")
logger.setLevel(logging.INFO)

# Eğer handler zaten varsa tekrar ekleme
if not logger.handlers:
    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(module)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler (Rotating, Max 5MB, 3 Yedek)
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def log_info(msg: str):
    logger.info(msg)

def log_error(msg: str):
    logger.error(msg)

def log_warning(msg: str):
    logger.warning(msg)

def log_critical(msg: str):
    logger.critical(msg)
