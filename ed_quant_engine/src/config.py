import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Initial Capital
INITIAL_CAPITAL = 10000.0

# Tickers Definition (Phase 1)
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],
    "FOREX": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CHFTRY=X"]
}
