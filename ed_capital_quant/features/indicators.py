"""
ED Capital Quant Engine - Feature Engineering Module
Calculates momentum, volatility, trend, and risk metrics using pandas-ta.
"""
import pandas as pd
import pandas_ta as ta
import numpy as np
from ..core.logger import logger

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Apply technical indicators safely without lookahead bias."""
    if df.empty or len(df) < 200:
        logger.warning(f"DataFrame too short for full indicator calculation (rows: {len(df)})")
        return pd.DataFrame()

    # Create a copy to prevent SettingWithCopyWarning
    df = df.copy()

    # 1. Trend Filter: EMA
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    # 2. Momentum: RSI & MACD
    df['RSI_14'] = ta.rsi(df['Close'], length=14)

    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    # pandas-ta macd returns a DataFrame with columns MACD_12_26_9, MACDh_12_26_9 (histogram), MACDs_12_26_9 (signal)
    df = pd.concat([df, macd], axis=1)

    # 3. Volatility & Risk Management: ATR & Bollinger Bands
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    bb = ta.bbands(df['Close'], length=20, std=2)
    # returns BBL_20_2.0 (lower), BBM_20_2.0 (mid), BBU_20_2.0 (upper), BBB_20_2.0 (bandwidth), BBP_20_2.0 (percent)
    df = pd.concat([df, bb], axis=1)

    # 4. Price Action: Log Returns
    df['Return_1d'] = np.log(df['Close'] / df['Close'].shift(1))

    # Shift all features by 1 to prevent lookahead bias (we only trade on closed candles)
    shifted_cols = ['EMA_50', 'EMA_200', 'RSI_14', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
                    'ATR_14', 'BBL_20_2.0', 'BBU_20_2.0', 'Return_1d']

    for col in shifted_cols:
        if col in df.columns:
            df[f'{col}_prev'] = df[col].shift(1)

    # Drop NaNs created by lookback periods and shifts
    df.dropna(inplace=True)

    return df
