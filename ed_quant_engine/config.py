import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
    MODE = os.getenv("MODE", "PAPER")

    DB_PATH = "paper_db.sqlite3"
    LOG_PATH = "logs/quant_engine.log"
    MODEL_PATH = "models/rf_model.pkl"
    REPORT_DIR = "reports/"

    # Universe
    TICKERS = {
        "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
        "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
        "Softs": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
        "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"],
        "Macro": ["DX-Y.NYB", "^TNX", "^VIX"]
    }

    ALL_TICKERS = [t for cat in TICKERS.values() for t in cat]

    # Risk Limits
    MAX_PORTFOLIO_RISK_PCT = 0.06 # Max 6% total risk
    MAX_OPEN_POSITIONS = 4
    BASE_CAPITAL = 10000.0
