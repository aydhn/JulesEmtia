import pandas as pd
import pandas_ta as ta
import numpy as np
from src.core.logger import logger

def add_features(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    """
    Adds technical indicators to the DataFrame using pandas_ta.
    Optimized for vectorization and strict lookahead bias protection.
    """
    try:
        df = df.copy()

        # Ensure we have OHLCV columns
        close_col = f"{prefix}Close" if prefix else "Close"
        high_col = f"{prefix}High" if prefix else "High"
        low_col = f"{prefix}Low" if prefix else "Low"

        if close_col not in df.columns:
             logger.warning(f"Missing Close column for features. Present: {df.columns}")
             return df

        # Trend Filters: EMA 50, EMA 200
        df[f'{prefix}EMA_50'] = ta.ema(df[close_col], length=50)
        df[f'{prefix}EMA_200'] = ta.ema(df[close_col], length=200)

        # Momentum: RSI (14), MACD
        df[f'{prefix}RSI_14'] = ta.rsi(df[close_col], length=14)
        macd = ta.macd(df[close_col], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df = pd.concat([df, macd.add_prefix(prefix)], axis=1)

        # Volatility: ATR (14), Bollinger Bands (20, 2)
        df[f'{prefix}ATR_14'] = ta.atr(df[high_col], df[low_col], df[close_col], length=14)
        bbands = ta.bbands(df[close_col], length=20, std=2)
        if bbands is not None and not bbands.empty:
            df = pd.concat([df, bbands.add_prefix(prefix)], axis=1)

        # Price Action (Log Returns)
        df[f'{prefix}Log_Return'] = np.log(df[close_col] / df[close_col].shift(1))

        # Strict NaN Management: Drop rows where lookback periods caused NaNs
        df.dropna(inplace=True)
        return df
    except Exception as e:
        logger.error(f"Error adding features: {e}")
        return df
