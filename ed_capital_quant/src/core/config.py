import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

DB_PATH = "data/paper_db.sqlite3"
LOG_PATH = "logs/quant_engine.log"

# Define the Universe
TICKERS = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"]
}

ALL_TICKERS = [ticker for category in TICKERS.values() for ticker in category]

INITIAL_CAPITAL = 10000.0

# Trading settings
MAX_TOTAL_RISK_PERCENT = 0.06
MAX_OPEN_POSITIONS = 4
CORRELATION_THRESHOLD = 0.75
VIX_THRESHOLD = 30.0
Z_SCORE_ANOMALY = 4.0
MIN_WFE = 0.50
ML_PROB_THRESHOLD = 0.60
SENTIMENT_THRESHOLD = -0.50

# Spread/Slippage dictionary
SPREADS = {
    "Metals": 0.0005,
    "Energy": 0.0005,
    "Agriculture": 0.0010,
    "Forex_TRY": 0.0015
}

def get_base_spread(ticker: str) -> float:
    for category, tickers in TICKERS.items():
        if ticker in tickers:
            return SPREADS.get(category, 0.001)
    return 0.001
