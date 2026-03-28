import pandas as pd
import yfinance as yf
import requests
import json
import logging
import asyncio
from typing import Dict, Any, List

# Yfinance Log Seviyesini Gizle (Warnings)
logger = logging.getLogger("yfinance")
logger.setLevel(logging.CRITICAL)

from core.logger import logger as ed_logger

# Phase 1 Genişletilmiş Evren
TICKERS = {
    # Değerli Madenler
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Platinum": "PL=F",
    "Palladium": "PA=F",
    # Enerji
    "Crude_Oil": "CL=F",
    "Brent_Oil": "BZ=F",
    "Natural_Gas": "NG=F",
    # Tarım
    "Wheat": "ZW=F",
    "Corn": "ZC=F",
    "Soybean": "ZS=F",
    "Coffee": "KC=F",
    "Sugar": "SB=F",
    "Cotton": "CT=F",
    # TL Bazlı Forex (Majör/Minör Karışık)
    "USDTRY": "USDTRY=X",
    "EURTRY": "EURTRY=X",
    "GBPTRY": "GBPTRY=X",
    "JPYTRY": "JPYTRY=X",
    "CNHTRY": "CNHTRY=X"
}

# Makro Ekonomik Veriler (DXY, 10-Yıllık Tahvil, VIX)
MACRO_TICKERS = {
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "VIX": "^VIX"
}

def load_environment() -> Dict[str, str]:
    from dotenv import load_dotenv
    import os
    load_dotenv()

    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "admin_chat_id": os.getenv("ADMIN_CHAT_ID"),
        "initial_capital": float(os.getenv("INITIAL_CAPITAL", 10000.0))
    }