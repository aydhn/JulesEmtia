import pandas as pd
import pandas_ta as ta

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    # Hourly timeframe indicators
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    df['Returns'] = df['Close'].pct_change()

    # Calculate daily indicators if daily price exists
    if 'Close_HTF' in df.columns:
        df.ta.ema(close=df['Close_HTF'], length=50, suffix='HTF', append=True)
        df.ta.ema(close=df['Close_HTF'], length=200, suffix='HTF', append=True)
        df.ta.macd(close=df['Close_HTF'], fast=12, slow=26, signal=9, suffix='HTF', append=True)
        df.ta.rsi(close=df['Close_HTF'], length=14, suffix='HTF', append=True)
        df['Returns_HTF'] = df['Close_HTF'].pct_change()

    df.dropna(inplace=True)
    return df
