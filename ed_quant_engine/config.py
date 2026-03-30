import os
from dotenv import load_dotenv

load_dotenv()

# --- SECURITY ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TOKEN_HERE")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "YOUR_CHAT_ID")

# --- UNIVERSE ---
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHTRY=X", "CHFTRY=X", "AUDTRY=X"]
}

# --- RISK PARAMETERS ---
INITIAL_CAPITAL = 10000.0
MAX_POSITIONS = 3
MAX_RISK_PER_TRADE = 0.02
GLOBAL_EXPOSURE_LIMIT = 0.06 # %6
CORRELATION_THRESHOLD = 0.75

# --- SYSTEM PARAMETERS ---
VIX_PANIC_THRESHOLD = 30.0
Z_SCORE_ANOMALY = 4.0
SENTIMENT_VETO_THRESHOLD = -0.50
