import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "dummy_token")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "dummy_id")

# Phase 1: Ticker Universe
TICKERS = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F"],
    "Agri": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],
    "Forex": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNH=F"]
}
FLAT_TICKERS = [tick for sublist in TICKERS.values() for tick in sublist]

# JP Morgan Risk Parameters
MAX_GLOBAL_EXPOSURE = 0.06
MAX_OPEN_POSITIONS = 4
MAX_RISK_PER_TRADE = 0.02
KELLY_FRACTION = 0.5
CORRELATION_THRESHOLD = 0.75
VIX_BLACK_SWAN_THRESHOLD = 30.0
Z_SCORE_ANOMALY = 4.0
