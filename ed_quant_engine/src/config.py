import os

# Universe (Tickers)
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F"],
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHTRY=X", "CHFTRY=X", "AUDTRY=X"]
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

# Telegram Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Portfolio Config
INITIAL_BALANCE = 10000.0
MAX_POSITIONS = 4
MAX_GLOBAL_RISK_PCT = 0.06
MAX_SINGLE_RISK_CAP = 0.04
CORRELATION_THRESHOLD = 0.75
