import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Tuple

def add_features(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
    """
    Computes technical indicators natively using pandas and numpy (pandas_ta is used internally for speed).
    Zero Lookahead Bias rule applied: Features are calculated on past data only.
    """
    if df.empty:
        return df

    # We make a copy to avoid SettingWithCopy warnings
    data = df.copy()

    # Rename columns to standardized names just in case yfinance gives uppercase
    data.columns = [c.lower() for c in data.columns]

    # Required columns check
    required = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in data.columns for col in required):
        return data

    # 1. Trend Filters (EMA 50 & 200)
    data['ema_50'] = data.ta.ema(length=50)
    data['ema_200'] = data.ta.ema(length=200)

    # 2. Momentum & Overbought/Oversold (RSI 14 & MACD 12,26,9)
    data['rsi_14'] = data.ta.rsi(length=14)
    macd = data.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        data['macd'] = macd['MACD_12_26_9']
        data['macd_hist'] = macd['MACDh_12_26_9']
        data['macd_signal'] = macd['MACDs_12_26_9']

    # 3. Volatility & Risk Management (ATR 14 & Bollinger Bands 20,2)
    data['atr_14'] = data.ta.atr(length=14)
    bbands = data.ta.bbands(length=20, std=2)
    if bbands is not None and not bbands.empty:
        data['bb_lower'] = bbands['BBL_20_2.0']
        data['bb_middle'] = bbands['BBM_20_2.0']
        data['bb_upper'] = bbands['BBU_20_2.0']

    # 4. Price Action (Log Returns)
    # Using previous close to calculate returns to strictly prevent lookahead
    data['log_return'] = np.log(data['close'] / data['close'].shift(1))

    # Shift indicators down by 1 row to prevent Lookahead Bias when generating signals.
    # The signal at row 'i' must ONLY use indicator values known at row 'i-1'.
    cols_to_shift = [
        'ema_50', 'ema_200', 'rsi_14', 'macd', 'macd_hist', 'macd_signal',
        'atr_14', 'bb_lower', 'bb_middle', 'bb_upper', 'log_return'
    ]

    # Actually, shifting indicators here causes confusion in backtesting if we aren't careful.
    # The professional quant approach is: the indicators are recorded AS OF the close of the candle.
    # We will enforce the `.shift(1)` logic inside the *Strategy* module, not the *Features* module.
    # This keeps features.py clean and purely mathematical.

    # Drop NaNs created by rolling windows (e.g., first 200 rows for EMA_200)
    data.dropna(subset=['ema_200', 'atr_14'], inplace=True)

    return data

def align_timeframes(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aligns HTF (Daily) and LTF (Hourly) data.
    CRITICAL: Lookahead bias prevention. We use `merge_asof` with direction='backward'.
    This ensures that at 14:00 on Day N, we only see the Daily Close of Day N-1.
    """
    if htf_df.empty or ltf_df.empty:
        return pd.DataFrame()

    htf = htf_df.copy()
    ltf = ltf_df.copy()

    # Ensure datetime indices
    htf.index = pd.to_datetime(htf.index)
    ltf.index = pd.to_datetime(ltf.index)

    # Prefix HTF columns
    htf.columns = [f"htf_{c}" for c in htf.columns]

    # Merge ASOF
    htf.reset_index(inplace=True)
    ltf.reset_index(inplace=True)

    # We must shift HTF by 1 period before merging so today's hourly candles only see yesterday's daily candle.
    # This is the ultimate defense against MTF lookahead bias.
    htf_shifted = htf.copy()
    date_col = htf_shifted.columns[0] # Usually 'Date' or 'index'
    # Shift values but keep dates
    values_to_shift = [c for c in htf_shifted.columns if c != date_col]
    htf_shifted[values_to_shift] = htf_shifted[values_to_shift].shift(1)
    htf_shifted.dropna(inplace=True)

    merged = pd.merge_asof(
        ltf.sort_values(ltf.columns[0]),
        htf_shifted.sort_values(date_col),
        left_on=ltf.columns[0],
        right_on=date_col,
        direction='backward'
    )

    # Set the LTF date back as index
    merged.set_index(ltf.columns[0], inplace=True)
    if date_col in merged.columns:
        merged.drop(columns=[date_col], inplace=True)

    return merged
