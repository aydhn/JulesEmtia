import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "DUMMY_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "123456789")
DB_PATH = "data/paper_db.sqlite3"
MODEL_PATH = "models/rf_model.pkl"

TICKERS = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agri": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
    "Forex": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CHFTRY=X", "AUDTRY=X", "CNHTRY=X"]
}

# Combine all into a single list
ALL_TICKERS = [t for group in TICKERS.values() for t in group]
