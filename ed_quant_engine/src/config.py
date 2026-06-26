from __future__ import annotations

import os

from dotenv import load_dotenv

from src.paths import ENV_PATH, ensure_runtime_dirs


ensure_runtime_dirs()
load_dotenv(ENV_PATH)

# Universe (Tickers)
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CHFTRY=X", "AUDTRY=X"]
    # NOTE: CNHTRY=X is not available on yfinance. CNH/TRY cross can be derived
    # from CNYUSD=X * USDTRY=X in future enhancement.
}

# Ticker Flat List
ALL_TICKERS = [ticker for category in UNIVERSE.values() for ticker in category]

# Spread Config (%)
SPREADS = {
    "Metals": 0.0002,      # 0.02%
    "Energy": 0.0002,      # 0.02%
    "Agriculture": 0.0005, # 0.05%
    "Forex_TRY": 0.0010    # 0.10%
}

def get_spread(ticker: str) -> float:
    for category, tickers in UNIVERSE.items():
        if ticker in tickers:
            return SPREADS.get(category, 0.0005)
    return 0.0005

# Macro Parameters
VIX_TICKER = "^VIX"
DXY_TICKER = "DX-Y.NYB"
US10Y_TICKER = "^TNX"
VIX_THRESHOLD = 30.0
Z_SCORE_THRESHOLD = 4.0

# Telegram Config. TELEGRAM_CHAT_ID is kept as a read-only compatibility alias.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = (os.getenv("ADMIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()

# Portfolio Config
INITIAL_BALANCE = 10000.0
MAX_POSITIONS = 4
MAX_GLOBAL_RISK_PCT = 0.06
MAX_SINGLE_RISK_CAP = 0.04
CORRELATION_THRESHOLD = 0.75

# Runtime and model governance
MIN_RF_PROBABILITY = 0.55
MIN_RF_OOS_ACCURACY = 0.52
MIN_TRAINING_ROWS = 500
PPO_MIN_ROWS = 300
PPO_BOOTSTRAP_TIMESTEPS = int(os.getenv("JULESEMTIA_PPO_BOOTSTRAP_STEPS", "5000"))
PPO_ROUTINE_TIMESTEPS = int(os.getenv("JULESEMTIA_PPO_ROUTINE_STEPS", "2500"))
TRAINING_BOOTSTRAP_SLEEP_SECONDS = int(os.getenv("JULESEMTIA_TRAINING_BOOTSTRAP_SLEEP", "60"))
TRAINING_ROUTINE_SLEEP_SECONDS = int(os.getenv("JULESEMTIA_TRAINING_ROUTINE_SLEEP", "300"))
INGEST_CONCURRENCY = int(os.getenv("JULESEMTIA_INGEST_CONCURRENCY", "4"))
AUTO_STOP_SECONDS = int(os.getenv("JULESEMTIA_AUTO_STOP_SECONDS", "0") or "0")
