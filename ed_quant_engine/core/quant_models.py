import pandas as pd
import pandas_ta as ta
import numpy as np
from .infrastructure import logger

# ----------------- TECHNICAL INDICATORS (Phase 3) -----------------
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add MTF indicators using vectorized pandas_ta operations."""
    if len(df) < 200:
        logger.warning(f"Dataframe too short ({len(df)}) for features.")
        return df

    # Trend Filter (EMA 50 & 200)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)

    # Momentum & RSI
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)

    # Additional Momentum (MFI, OBV, CMF, Supertrend)
    df.ta.mfi(length=14, append=True)
    df.ta.obv(append=True)
    df.ta.cmf(length=20, append=True)
    df.ta.supertrend(length=7, multiplier=3.0, append=True)

    # ADX Trend Strength
    df.ta.adx(length=14, append=True)

    # Volatility & Risk (ATR & BBands)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)

    # Micro Flash Crash Detection (Phase 19 Z-Score)
    sma = df['Close'].rolling(window=20).mean()
    std = df['Close'].rolling(window=20).std()
    df['Z_Score'] = (df['Close'] - sma) / std

    # Price Action (Log Returns)
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    # Uyumsuzluk (Divergence) Detection (Price vs RSI/MACD/OBV)
    # Check if price makes lower low, but indicator makes higher low
    df['Price_Min'] = df['Low'].rolling(window=5, center=True).min()
    df['Price_Max'] = df['High'].rolling(window=5, center=True).max()

    price_diff = df['Close'].diff(periods=10)

    # RSI Divergence
    if 'RSI_14' in df.columns:
        rsi_diff = df['RSI_14'].diff(periods=10)
        df['Bullish_Div_RSI'] = (price_diff < 0) & (rsi_diff > 0) & (df['RSI_14'] < 40)
        df['Bearish_Div_RSI'] = (price_diff > 0) & (rsi_diff < 0) & (df['RSI_14'] > 60)

    # MACD Divergence
    if 'MACDh_12_26_9' in df.columns:
        macd_diff = df['MACDh_12_26_9'].diff(periods=10)
        df['Bullish_Div_MACD'] = (price_diff < 0) & (macd_diff > 0) & (df['MACDh_12_26_9'] < 0)
        df['Bearish_Div_MACD'] = (price_diff > 0) & (macd_diff < 0) & (df['MACDh_12_26_9'] > 0)

    # OBV Divergence
    if 'OBV' in df.columns:
        obv_diff = df['OBV'].diff(periods=10)
        df['Bullish_Div_OBV'] = (price_diff < 0) & (obv_diff > 0)
        df['Bearish_Div_OBV'] = (price_diff > 0) & (obv_diff < 0)

    df.dropna(inplace=True)
    return df
