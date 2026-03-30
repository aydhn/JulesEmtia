"""
ED Capital Quant Engine - Configuration Module
Vizyon: SIFIR BÜTÇE, Yüksek Win Rate, Kurumsal Risk Algısı.
"""
import os

# Telegram Configuration (must be set in .env)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "your_token_here")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "your_chat_id_here")

# Directory Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
MODEL_DIR = os.path.join(BASE_DIR, "models")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# Database Configuration
DB_PATH = os.path.join(DATA_DIR, "paper_db.sqlite3")

# Target Trading Universe
UNIVERSE = {
    "Metals": ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"],  # Altın, Gümüş, Bakır, Paladyum, Platin
    "Energy": ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"],  # WTI, Brent, Doğalgaz, Isınma Yağı, Benzin
    "Agriculture": ["ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F"],  # Tarım
    "Forex_TRY": ["USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHTRY=X", "CHFTRY=X", "AUDTRY=X"],
    "Benchmark": ["USDTRY=X", "^TNX", "DX-Y.NYB", "^VIX"]  # ABD 10 Yıllık, DXY, Korku Endeksi
}

def get_all_tickers() -> list:
    tickers = []
    for cat, items in UNIVERSE.items():
        if cat != "Benchmark":
            tickers.extend(items)
    return tickers

# Risk & Quant Parameters
MAX_GLOBAL_RISK_PCT = 0.06      # Kasanın max %6'sı toplam riskte olabilir
MAX_OPEN_POSITIONS = 4          # Maksimum açık pozisyon limiti
MAX_SINGLE_TRADE_CAP = 0.04     # Bir işlemde kasa max %4 risk alabilir
CORRELATION_THRESHOLD = 0.75    # 0.75 üzeri korelasyon varsa işlem reddedilir
VIX_CIRCUIT_BREAKER = 30.0      # VIX bu değeri geçerse Siyah Kuğu rejimi tetiklenir
ML_CONFIDENCE_THRESHOLD = 0.60  # Makine öğrenmesi %60 altı başarı öngörürse reddet

# Spread & Slippage Base Costs
SPREADS = {
    "Metals": 0.0002,     # %0.02
    "Energy": 0.0002,
    "Agriculture": 0.0005,
    "Forex_TRY": 0.0010   # %0.10 (Likit olmayan zamanlarda artar)
}
