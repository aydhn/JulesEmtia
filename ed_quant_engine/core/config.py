import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))

# ED Capital Kurumsal İşlem Evreni (Genişletilmiş)
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI":   ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "GF=F", "HE=F"],
    "FOREX":  ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNYTRY=X", "CHFTRY=X", "AUDTRY=X"]
}

# Spread ve Makas Simülasyonu (Phase 21)
SPREADS = {"METALS": 0.0002, "ENERGY": 0.0003, "AGRI": 0.0005, "FOREX": 0.0010}

# Portföy ve Risk Yönetimi (Phase 11, 15)
INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE = 0.04 # Hard Cap %4 (Fractional Kelly tavanı)
GLOBAL_EXPOSURE_LIMIT = 4 # Maks. açık pozisyon (Toplam risk %16)
CORRELATION_THRESHOLD = 0.75 # Maksimum izin verilen korelasyon

# Devre Kesici (Phase 19)
VIX_THRESHOLD = 35.0
Z_SCORE_THRESHOLD = 4.0

# NLP (Phase 20)
SENTIMENT_THRESHOLD_LONG = -0.3
SENTIMENT_THRESHOLD_SHORT = 0.3
