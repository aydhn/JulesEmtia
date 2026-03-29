import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Ticker Universe
TICKERS = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"]
}

# General Configuration
DB_PATH = "paper_db.sqlite3"
MODEL_PATH = "models/rf_model.pkl"

# Risk Management
MAX_PORTFOLIO_RISK_PCT = 0.06
MAX_OPEN_POSITIONS = 4
CORRELATION_THRESHOLD = 0.75
VIX_THRESHOLD = 30.0

# Initial Capital
INITIAL_CAPITAL = 10000.0
