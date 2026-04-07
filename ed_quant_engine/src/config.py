import os

# Ticker Universe
TICKERS = {
    # Precious Metals
    "GC=F": "Gold", "SI=F": "Silver", "HG=F": "Copper", "PA=F": "Palladium", "PL=F": "Platinum",
    # Energy
    "CL=F": "WTI Crude", "BZ=F": "Brent", "NG=F": "Natural Gas", "HO=F": "Heating Oil", "RB=F": "Gasoline",
    # Agriculture
    "ZW=F": "Wheat", "ZC=F": "Corn", "ZS=F": "Soybeans", "KC=F": "Coffee", "CC=F": "Cocoa", "SB=F": "Sugar", "CT=F": "Cotton", "LE=F": "Live Cattle",
    # Forex (TRY specific)
    "USDTRY=X": "USD/TRY", "EURTRY=X": "EUR/TRY", "GBPTRY=X": "GBP/TRY", "JPYTRY=X": "JPY/TRY", "CNHTRY=X": "CNH/TRY", "CHFTRY=X": "CHF/TRY"
}

# Bot Constraints
STARTING_BALANCE = 10000.0
MAX_POSITIONS = 4
MAX_GLOBAL_RISK_PCT = 0.06  # Max 6% of total capital across all positions

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Ensure dirs exist
for d in [DATA_DIR, MODELS_DIR, LOGS_DIR, REPORTS_DIR]:
    os.makedirs(d, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "paper_db.sqlite3")
