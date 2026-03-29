import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

# Phase 1: Expanded Trading Universe (Tickers)
UNIVERSE: Dict[str, List[str]] = {
    "metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"], # Gold, Silver, Copper, Palladium, Platinum
    "energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"], # WTI, Brent, Natural Gas, Heating Oil, RBOB Gasoline
    "agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"], # Wheat, Corn, Soybeans, Coffee, Cocoa, Sugar, Cotton, Live Cattle, Lean Hogs
    "forex_try": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNYTRY=X", "CHFTRY=X", "AUDTRY=X"],
    "macro": ["DX-Y.NYB", "^TNX", "^VIX"] # DXY, US 10Y Yield, VIX
}

# Notification & Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "paper_db.sqlite3")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
MODELS_DIR = os.path.join(BASE_DIR, "models")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

for directory in [os.path.dirname(DB_PATH), LOGS_DIR, MODELS_DIR, REPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# Risk & Strategy Defaults
INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE = 0.02 # 2% default, can be overridden by Kelly
GLOBAL_MAX_EXPOSURE = 0.06 # 6% total portfolio exposure limit
MAX_OPEN_POSITIONS = 3
CORRELATION_THRESHOLD = 0.75

# Indicator Parameters
EMA_FAST = 50
EMA_SLOW = 200
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
ATR_PERIOD = 14

# Dynamic Stop & Profit parameters (ATR multipliers)
SL_ATR_MULTIPLIER = 1.5
TP_ATR_MULTIPLIER = 3.0
TRAILING_STOP_ATR = 1.5
BREAKEVEN_TRIGGER_ATR = 1.0

# Macro & Circuit Breakers
VIX_CRITICAL_LEVEL = 35.0
Z_SCORE_FLASH_CRASH = 4.0

# Machine Learning
RF_PROBABILITY_THRESHOLD = 0.60
RF_LOOKAHEAD_TARGET = 10 # Predict success within next 10 bars

# Execution & Modeling
DEFAULT_SLIPPAGE_PCT = 0.001 # 0.1%
