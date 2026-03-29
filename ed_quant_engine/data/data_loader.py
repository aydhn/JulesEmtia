import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from core.logger import get_logger
logger = get_logger()

def exponential_backoff(func):
    def wrapper(*args, **kwargs):
        retries = 3
        delay = 2
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Veri çekme hatası (Deneme {i+1}/{retries}): {e}")
                if i == retries - 1:
                    logger.error("API Limit Aşıldı veya Bağlantı Koptu.")
                    return None
                time.sleep(delay)
                delay *= 2
    return wrapper

class DataLoader:
    def __init__(self):
        pass

    @exponential_backoff
    def fetch_mtf_data(self, ticker: str) -> pd.DataFrame:
        htf = yf.download(ticker, interval="1d", period="2y", progress=False)
        ltf = yf.download(ticker, interval="1h", period="1mo", progress=False)

        if htf.empty or ltf.empty: return None

        htf['EMA_50'] = ta.ema(htf['Close'], length=50)
        macd = ta.macd(htf['Close'])
        htf['MACD'] = macd.iloc[:, 0] if macd is not None else 0
        htf['HTF_Trend'] = np.where((htf['Close'] > htf['EMA_50']) & (htf['MACD'] > 0), 1,
                           np.where((htf['Close'] < htf['EMA_50']) & (htf['MACD'] < 0), -1, 0))

        htf_shifted = htf[['HTF_Trend', 'EMA_50']].shift(1).dropna()

        ltf['RSI'] = ta.rsi(ltf['Close'], length=14)
        ltf['ATR'] = ta.atr(ltf['High'], ltf['Low'], ltf['Close'], length=14)
        ltf['Returns'] = ltf['Close'].pct_change()

        # Z-Score Flaş çöküş
        ltf['Z_Score'] = (ltf['Close'] - ltf['Close'].rolling(50).mean()) / ltf['Close'].rolling(50).std()

        ltf = ltf.reset_index()
        htf_shifted = htf_shifted.reset_index()

        if ltf['Datetime'].dt.tz is not None:
            ltf['Datetime'] = ltf['Datetime'].dt.tz_localize(None)
        if htf_shifted['Date'].dt.tz is not None:
            htf_shifted['Date'] = htf_shifted['Date'].dt.tz_localize(None)

        htf_shifted = htf_shifted.rename(columns={'Date': 'Datetime'})

        merged = pd.merge_asof(ltf, htf_shifted, on='Datetime', direction='backward')
        return merged.set_index('Datetime').dropna()
