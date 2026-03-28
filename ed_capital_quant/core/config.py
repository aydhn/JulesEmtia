import os
from dotenv import load_dotenv

load_dotenv()

# Trading Universe (Tickers)
UNIVERSE = {
    'METALS': ['GC=F', 'SI=F', 'HG=F', 'PA=F', 'PL=F'],
    'ENERGY': ['CL=F', 'BZ=F', 'NG=F', 'HO=F', 'RB=F'],
    'AGRICULTURE': ['ZW=F', 'ZC=F', 'ZS=F', 'KC=F', 'CC=F', 'SB=F', 'CT=F'],
    'FOREX_TRY': ['USDTRY=X', 'EURTRY=X', 'GBPTRY=X', 'JPYTRY=X', 'CNYTRY=X', 'CHFTRY=X', 'AUDTRY=X'],
}

SPREADS = {"METALS": 0.0002, "ENERGY": 0.0003, "AGRICULTURE": 0.0005, "FOREX_TRY": 0.0010}

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

DB_NAME = 'paper_db.sqlite3'
LOG_DIR = 'logs'
MODELS_DIR = 'models'

# Risk Parameters
INITIAL_CAPITAL = 10000.0
MAX_OPEN_POSITIONS = 3
MAX_GLOBAL_EXPOSURE = 0.06
MAX_CORRELATION = 0.75

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
