import pandas as pd
import pandas_ta as ta
import numpy as np

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates high-accuracy, zero lookahead-bias technical indicators using pandas_ta."""
    # Ensure there's enough data
    if len(df) < 200:
        return df

    # Copy the df so we don't accidentally modify the original data source
    df_copy = df.copy()

    # Calculate EMAs for Trend
    df_copy.ta.ema(length=50, append=True)
    df_copy.ta.ema(length=200, append=True)

    # Momentum
    df_copy.ta.rsi(length=14, append=True)
    df_copy.ta.macd(fast=12, slow=26, signal=9, append=True)

    # Volatility / Risk Profile
    df_copy.ta.atr(length=14, append=True)
    df_copy.ta.bbands(length=20, std=2, append=True)

    # Price Action
    df_copy['Log_Return'] = np.log(df_copy['Close'] / df_copy['Close'].shift(1))

    # Clean up NaNs created by 'lookbacks' from EMAs
    df_copy.dropna(inplace=True)

    return df_copy
