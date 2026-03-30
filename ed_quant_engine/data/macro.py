import yfinance as yf
import pandas as pd
import time
from core.logger import get_logger

log = get_logger()

def get_vix():
    try:
        vix = yf.download('^VIX', period='5d', interval='1d', progress=False)
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [col[0] for col in vix.columns]
        if not vix.empty:
            return vix['Close'].iloc[-1]
    except Exception as e:
        log.error(f"Error fetching VIX: {e}")
    return 20.0 # Default safe VIX if fetch fails

def get_dxy_trend():
    try:
        dxy = yf.download('DX-Y.NYB', period='1mo', interval='1d', progress=False)
        if isinstance(dxy.columns, pd.MultiIndex):
            dxy.columns = [col[0] for col in dxy.columns]
        if len(dxy) > 10:
            dxy['EMA_10'] = dxy['Close'].ewm(span=10, adjust=False).mean()
            return 'UP' if dxy['Close'].iloc[-1] > dxy['EMA_10'].iloc[-1] else 'DOWN'
    except Exception as e:
        log.error(f"Error fetching DXY: {e}")
    return 'NEUTRAL'
