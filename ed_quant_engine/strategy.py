import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from logger import log

def check_entry_signal(df_aligned: pd.DataFrame, ticker: str) -> Optional[Dict]:
    """
    Generates trading signals based on Multi-Timeframe (MTF) confluence.
    Requires HTF (Daily) and LTF (Hourly) alignment.
    Returns: Signal Dictionary if valid, else None.
    """
    if df_aligned is None or df_aligned.empty or len(df_aligned) < 2:
        return None

    # We always use the PREVIOUS closed candle (shift 1 conceptually, but df[-1] is latest closed in our setup)
    # Ensure we are not looking at an unclosed candle. Assuming df_aligned[-1] is fully closed.
    current = df_aligned.iloc[-1]

    # Check for NaNs in critical fields
    required_cols = ['Close', 'EMA_50', 'RSI_14', 'MACD_hist', 'HTF_Close', 'HTF_EMA_50']
    for col in required_cols:
        if col not in current or pd.isna(current[col]):
            return None

    signal = None

    # --- LONG LOGIC ---
    # HTF Filter: Daily Close > Daily EMA 50
    is_htf_bullish = current['HTF_Close'] > current['HTF_EMA_50']

    # LTF Trigger: Hourly Price > Hourly EMA 50 AND (RSI crossing up from 30 OR touching lower BB)
    is_ltf_bullish = current['Close'] > current['EMA_50']
    rsi_oversold = current['RSI_14'] < 40 # Relaxed for testing, usually 30
    macd_bullish = current['MACD_hist'] > 0

    if is_htf_bullish and is_ltf_bullish and rsi_oversold and macd_bullish:
        signal = "Long"

    # --- SHORT LOGIC ---
    is_htf_bearish = current['HTF_Close'] < current['HTF_EMA_50']
    is_ltf_bearish = current['Close'] < current['EMA_50']
    rsi_overbought = current['RSI_14'] > 60 # Usually 70
    macd_bearish = current['MACD_hist'] < 0

    if is_htf_bearish and is_ltf_bearish and rsi_overbought and macd_bearish:
        signal = "Short"

    if not signal:
        return None

    # Calculate ATR-based dynamic Stops
    atr = current['ATR_14']
    entry_price = current['Close']

    if signal == "Long":
        sl = entry_price - (1.5 * atr)
        tp = entry_price + (3.0 * atr)
    else:
        sl = entry_price + (1.5 * atr)
        tp = entry_price - (3.0 * atr)

    return {
        "ticker": ticker,
        "direction": signal,
        "entry_price": entry_price,
        "sl": sl,
        "tp": tp,
        "atr": atr
    }
