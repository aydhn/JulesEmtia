import os
import logging
from dotenv import load_dotenv

load_dotenv()

# System Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DB_PATH = os.getenv("DB_PATH", "paper_db.sqlite3")

# Setup Logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            "logs/quant_engine.log", maxBytes=5 * 1024 * 1024, backupCount=3
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("EDCapitalQuant")

# Trading Universe
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"],
    "Macro": ["DX-Y.NYB", "^TNX", "^VIX"]
}

# Base Spread Dictionary (Percentage)
BASE_SPREADS = {
    "Metals": 0.0002,      # 0.02%
    "Energy": 0.0003,      # 0.03%
    "Agriculture": 0.0005, # 0.05%
    "Forex_TRY": 0.0010,   # 0.10%
    "Macro": 0.0         # Not traded directly
}

def get_asset_class(ticker: str) -> str:
    for asset_class, tickers in UNIVERSE.items():
        if ticker in tickers:
            return asset_class
    return "Forex_TRY"  # Fallback

# Portfolio Limits
STARTING_BALANCE = 10000.0
MAX_PORTFOLIO_RISK_PCT = 0.06  # 6% total risk max
MAX_OPEN_POSITIONS = 4
MAX_CORRELATION_THRESHOLD = 0.75
VIX_PANIC_THRESHOLD = 30.0

# MTF Timelines
HTF_INTERVAL = "1d"
LTF_INTERVAL = "1h"

# Kelly Settings
MAX_FRACTIONAL_KELLY_CAP = 0.04 # Max 4% per trade
KELLY_MULTIPLIER = 0.5 # Half-Kelly

# Machine Learning
ML_PROBA_THRESHOLD = 0.60
