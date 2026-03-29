import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Any, List, Optional
from ed_quant_engine.logger import log
from ed_quant_engine.config import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD
)

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates all technical indicators and ensures NO Lookahead Bias."""
    df = df.copy()

    # Log Returns (Price Action)
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    # EMAs for Trend Filtering
    df.ta.ema(length=EMA_FAST, append=True)
    df.ta.ema(length=EMA_SLOW, append=True)

    # RSI for Momentum & Mean Reversion
    df.ta.rsi(length=RSI_PERIOD, append=True)

    # MACD for Momentum Confirmation
    df.ta.macd(append=True)

    # ATR for Risk Management & Trailing Stops
    df.ta.atr(length=ATR_PERIOD, append=True)

    # Bollinger Bands for Volatility / Mean Reversion
    df.ta.bbands(append=True)

    # VERY CRITICAL: Shift all features by 1 to prevent lookahead bias!
    # Signals generated on today's close should only use yesterday's closed candle.
    # We create a specific feature set that represents "Confirmed End Of Last Bar"

    # List all newly created columns
    feature_cols = [c for c in df.columns if c not in ['Open', 'High', 'Low', 'Close', 'Volume']]

    for col in feature_cols:
        df[col] = df[col].shift(1)

    # Drop NaNs resulting from lookback periods and shifts
    df.dropna(inplace=True)

    log.debug(f"Added {len(feature_cols)} shifted features. Shape: {df.shape}")
    return df

def align_mtf_data(daily_df: pd.DataFrame, hourly_df: pd.DataFrame) -> pd.DataFrame:
    """Merges Daily (HTF) features into Hourly (LTF) df without lookahead bias."""

    if daily_df is None or hourly_df is None or daily_df.empty or hourly_df.empty:
        return None

    # We must ensure that the hourly candle only sees the DAILY candle that closed *before* the hourly candle started.
    # We do this using merge_asof, matching the hourly index to the daily index.
    # direction='backward' ensures we only get the latest daily data that is strictly <= the hourly timestamp.
    # To be absolutely sure, we use the shifted daily features.

    daily_df = daily_df.copy()
    hourly_df = hourly_df.copy()

    # Make sure indexes are tz-aware or tz-naive consistently
    if hourly_df.index.tz is not None and daily_df.index.tz is None:
         daily_df.index = daily_df.index.tz_localize(hourly_df.index.tz)
    elif hourly_df.index.tz is None and daily_df.index.tz is not None:
         hourly_df.index = hourly_df.index.tz_localize(daily_df.index.tz)

    hourly_df.reset_index(inplace=True)
    daily_df.reset_index(inplace=True)

    # Sort indices just in case
    hourly_df.sort_values('Date', inplace=True)
    daily_df.sort_values('Date', inplace=True)

    # Rename daily columns to avoid overlap
    daily_cols = {c: f"HTF_{c}" for c in daily_df.columns if c != 'Date'}
    daily_df.rename(columns=daily_cols, inplace=True)

    # Merge!
    merged_df = pd.merge_asof(
        hourly_df,
        daily_df,
        on='Date',
        direction='backward',
        allow_exact_matches=False # The hourly candle closing exactly at the same time as daily shouldn't see it until next hour
    )

    merged_df.set_index('Date', inplace=True)
    merged_df.dropna(inplace=True)

    log.debug(f"MTF Data Aligned. Merged shape: {merged_df.shape}")
    return merged_df

if __name__ == "__main__":
    from ed_quant_engine.data_loader import fetch_data
    df = fetch_data("GC=F", "1d")
    if df is not None:
        features_df = add_features(df)
        print("Shifted Features:")
        print(features_df.tail())
