import pandas as pd
import pandas_ta as ta
import numpy as np

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 200:
        return df

    df = df.copy()

    # Trend Filter
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    # Momentum & Overbought/Oversold
    df['RSI_14'] = ta.rsi(df['Close'], length=14)
    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df['MACD'] = macd['MACD_12_26_9']
        df['MACDh'] = macd['MACDh_12_26_9']
        df['MACDs'] = macd['MACDs_12_26_9']

    # Volatility
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is not None and not bbands.empty:
        df['BBL'] = bbands['BBL_20_2.0']
        df['BBU'] = bbands['BBU_20_2.0']

    # Price Action
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    df.dropna(inplace=True)
    return df
