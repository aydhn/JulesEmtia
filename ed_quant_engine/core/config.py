import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))

# ED Capital Kurumsal İşlem Evreni
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI":   ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],
    "FOREX":  ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNYTRY=X", "CHFTRY=X"]
}

# Spread ve Makas Simülasyonu (Phase 21)
SPREADS = {"METALS": 0.0002, "ENERGY": 0.0003, "AGRI": 0.0005, "FOREX": 0.0010}

INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE = 0.04 # Hard Cap %4
GLOBAL_EXPOSURE_LIMIT = 4 # Maks. açık pozisyon
