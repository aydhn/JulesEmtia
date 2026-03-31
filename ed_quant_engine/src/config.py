import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Ticker Universe
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
    "FOREX_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"]
}

ALL_TICKERS = [ticker for category in TICKERS.values() for ticker in category]

DB_PATH = os.getenv("DB_PATH", "data/paper_db.sqlite3")
MODELS_PATH = os.getenv("MODELS_PATH", "models/")
LOGS_PATH = os.getenv("LOGS_PATH", "logs/")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MODELS_PATH, exist_ok=True)
os.makedirs(LOGS_PATH, exist_ok=True)
