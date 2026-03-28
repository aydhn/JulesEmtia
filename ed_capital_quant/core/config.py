import os
import json

# Global Configuration Constants
ENVIRONMENT = os.getenv("ENVIRONMENT", "PAPER") # PAPER or LIVE
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_storage")
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "paper_db.sqlite3")

# Strategy Parameters
MAX_GLOBAL_EXPOSURE_PCT = 0.06  # Max 6% of total portfolio exposed at any time
MAX_OPEN_POSITIONS = 4
CORRELATION_THRESHOLD = 0.75  # Threshold for vetoing highly correlated trades

# Kelly Criterion Settings
KELLY_FRACTION = 0.5  # Half-Kelly for JPM risk profile
MAX_RISK_PER_TRADE_PCT = 0.04 # Hard cap per trade: 4%

# Trading Universe
UNIVERSE = {
    # Precious Metals
    "GC=F": {"name": "Gold", "category": "Major_Metals", "base_spread_pct": 0.0002},
    "SI=F": {"name": "Silver", "category": "Major_Metals", "base_spread_pct": 0.0005},
    "HG=F": {"name": "Copper", "category": "Major_Metals", "base_spread_pct": 0.0005},
    "PA=F": {"name": "Palladium", "category": "Minor_Metals", "base_spread_pct": 0.0010},
    "PL=F": {"name": "Platinum", "category": "Minor_Metals", "base_spread_pct": 0.0010},

    # Energy
    "CL=F": {"name": "Crude Oil WTI", "category": "Energy", "base_spread_pct": 0.0003},
    "BZ=F": {"name": "Brent Crude", "category": "Energy", "base_spread_pct": 0.0003},
    "NG=F": {"name": "Natural Gas", "category": "Energy", "base_spread_pct": 0.0008},
    "RB=F": {"name": "RBOB Gasoline", "category": "Energy", "base_spread_pct": 0.0008},

    # Agriculture
    "ZW=F": {"name": "Wheat", "category": "Agriculture", "base_spread_pct": 0.0005},
    "ZC=F": {"name": "Corn", "category": "Agriculture", "base_spread_pct": 0.0005},
    "ZS=F": {"name": "Soybeans", "category": "Agriculture", "base_spread_pct": 0.0005},
    "KC=F": {"name": "Coffee", "category": "Agriculture", "base_spread_pct": 0.0010},
    "CC=F": {"name": "Cocoa", "category": "Agriculture", "base_spread_pct": 0.0010},
    "SB=F": {"name": "Sugar", "category": "Agriculture", "base_spread_pct": 0.0010},
    "CT=F": {"name": "Cotton", "category": "Agriculture", "base_spread_pct": 0.0010},

    # TRY based Forex
    "USDTRY=X": {"name": "USD/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0010},
    "EURTRY=X": {"name": "EUR/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0015},
    "GBPTRY=X": {"name": "GBP/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0015},
    "JPYTRY=X": {"name": "JPY/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0020},
    "CNHTRY=X": {"name": "CNH/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0020},
    "CHFTRY=X": {"name": "CHF/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0020},
    "AUDTRY=X": {"name": "AUD/TRY", "category": "Forex_Exotic", "base_spread_pct": 0.0020},
}
