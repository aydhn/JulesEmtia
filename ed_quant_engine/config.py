import os
import logging

# ==========================================
# ED CAPITAL QUANT ENGINE - CONFIGURATION
# ==========================================

# --- API & SECRETS ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

# --- UNIVERSE DEFINITION ---
TICKERS = {
    "METALS": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "ENERGY": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "AGRI": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"],
    "FOREX_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNYTRY=X", "CHFTRY=X", "AUDTRY=X"],
    "MACRO": ["DX-Y.NYB", "^TNX", "^VIX"]
}

# Flatten universe for easy scanning (excluding macro indicators which are handled separately)
ALL_TICKERS = TICKERS["METALS"] + TICKERS["ENERGY"] + TICKERS["AGRI"] + TICKERS["FOREX_TRY"]

# --- PORTFOLIO & RISK LIMITS ---
INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE_PCT = 0.02 # 2% max risk per trade
MAX_TOTAL_OPEN_RISK_PCT = 0.06 # 6% max global portfolio risk
MAX_OPEN_POSITIONS = 4
CORRELATION_THRESHOLD = 0.75 # Veto if correlation > 0.75
VIX_CIRCUIT_BREAKER_THRESHOLD = 35.0

# --- SPREAD & SLIPPAGE (Base Values in %) ---
SPREADS = {
    "METALS": 0.0005,  # 0.05%
    "ENERGY": 0.0008,
    "AGRI": 0.0010,
    "FOREX_TRY": 0.0015 # Higher spread for EM FX
}

# --- TIMEFRAMES ---
HTF = "1d" # Higher Timeframe
LTF = "1h" # Lower Timeframe

# --- LOGGING ---
LOG_FILE = "logs/quant_engine.log"
LOG_LEVEL = logging.INFO

# --- DATABASE ---
DB_PATH = "data/paper_db.sqlite3"
MODEL_PATH = "data/rf_model.pkl"

def get_spread_for_ticker(ticker: str) -> float:
    for category, tickers in TICKERS.items():
        if ticker in tickers and category in SPREADS:
            return SPREADS[category]
    return 0.0010 # Default
