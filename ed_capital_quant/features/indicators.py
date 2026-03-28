import pandas as pd
import pandas_ta as ta

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    df['Returns'] = df['Close'].pct_change()
    df.dropna(inplace=True)
    return df
