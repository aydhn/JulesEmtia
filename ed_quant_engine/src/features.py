import pandas as pd
import pandas_ta as ta
import numpy as np
from src.logger import logger

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators for the strategy.
    Expects a DataFrame with OHLCV columns.
    Uses pandas_ta for efficiency.
    Returns DataFrame with new columns.
    """

    # 1. Trend Filters (EMA)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    # 2. Momentum & Oscillators
    df['RSI_14'] = ta.rsi(df['Close'], length=14)
    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_Hist'] = macd['MACDh_12_26_9']
    df['MACD_Signal'] = macd['MACDs_12_26_9']

    # 3. Volatility & Risk (ATR & Bollinger Bands)
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    bbands = ta.bbands(df['Close'], length=20, std=2)
    df['BB_Lower'] = bbands['BBL_20_2.0']
    df['BB_Upper'] = bbands['BBU_20_2.0']
    df['BB_Mid'] = bbands['BBM_20_2.0']

    # 4. Price Action
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    # Forward fill then dropna to avoid lookahead bias and handle initial NaN rows
    df = df.ffill().dropna()

    return df

