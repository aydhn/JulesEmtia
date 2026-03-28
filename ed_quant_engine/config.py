import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Security
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# ED Capital Investment Universe
TICKERS = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNH=F", "CHFTRY=X"]
}

# Spread Assumptions (Base costs before ATR slippage)
SPREADS = {
    "Metals": 0.0002,      # Very liquid
    "Energy": 0.0003,
    "Agriculture": 0.0005,
    "Forex_TRY": 0.0010    # Exotic/Illiquid premium
}

# Global Risk Limits
MAX_OPEN_POSITIONS = 4
MAX_TOTAL_EXPOSURE_PCT = 0.06 # Max 6% of total capital across all positions
FRACTIONAL_KELLY = 0.5        # Half-Kelly for JP Morgan style risk mitigation
MAX_LOT_CAP_PCT = 0.04        # Hard cap: max 4% risk per single trade

# Timeframes
HTF = "1d"
LTF = "1h"

# System
DB_PATH = "data/paper_db.sqlite3"
MODEL_PATH = "models/rf_validator.pkl"
LOG_PATH = "logs/quant_engine.log"
