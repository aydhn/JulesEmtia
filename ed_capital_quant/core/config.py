"""
ED Capital Quant Engine - Configuration Module
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Trading Universe (Tickers)
UNIVERSE = {
    'METALS': ['GC=F', 'SI=F', 'HG=F', 'PA=F', 'PL=F'],
    'ENERGY': ['CL=F', 'BZ=F', 'NG=F', 'HO=F', 'RB=F'],
    'AGRICULTURE': ['ZW=F', 'ZC=F', 'ZS=F', 'KC=F', 'CC=F', 'SB=F', 'CT=F'],
    'FOREX_TRY': ['USDTRY=X', 'EURTRY=X', 'GBPTRY=X', 'JPYTRY=X', 'CNYTRY=X', 'CHFTRY=X', 'AUDTRY=X'],
    'MACRO': ['DX-Y.NYB', '^TNX', '^VIX'] # DXY, US10Y, VIX
}

# Config keys
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

DB_NAME = 'paper_db.sqlite3'
LOG_DIR = 'logs'
MODELS_DIR = 'models'

# Risk Parameters
RISK_PER_TRADE_PCT = 0.02
MAX_OPEN_POSITIONS = 3
MAX_PORTFOLIO_EXPOSURE_PCT = 0.06
MAX_DRAWDOWN_TOLERANCE_PCT = 0.15

VIX_PANIC_THRESHOLD = 30
FLASH_CRASH_Z_SCORE = 4.0

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
