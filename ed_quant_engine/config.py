# ED Capital Quant Engine - Master Configuration
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Phase 1: Genişletilmiş İşlem Evreni
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X", "CHFTRY=X", "AUDTRY=X"]
}

MACRO_TICKERS = {"DXY": "DX-Y.NYB", "US10Y": "^TNX", "VIX": "^VIX"}

INITIAL_CAPITAL = 10000.0
MAX_GLOBAL_EXPOSURE = 0.06 # Maksimum %6 Risk
MAX_POSITIONS = 4
CORRELATION_THRESHOLD = 0.75
VIX_PANIC_THRESHOLD = 35.0
ML_PROBABILITY_THRESHOLD = 0.60
SENTIMENT_VETO_THRESHOLD = -0.50
