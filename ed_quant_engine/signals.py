import pandas as pd
import numpy as np
from typing import Dict, Any
from logger import get_logger

log = get_logger()

def generate_signals(df: pd.DataFrame, is_mtf: bool = True) -> Dict[str, Any]:
    """
    Core Strategy Engine.
    MTF Confluence: HTF (Daily) determines trend, LTF (Hourly) determines entry.
    """
    latest = df.iloc[-1]

    # HTF Conditions (Trend Filtering)
    htf_trend_up = latest['Close_HTF'] > latest['EMA_50_HTF'] and latest['MACD_HTF'] > latest['MACD_Signal_HTF']
    htf_trend_down = latest['Close_HTF'] < latest['EMA_50_HTF'] and latest['MACD_HTF'] < latest['MACD_Signal_HTF']

    # LTF Conditions (Entry Trigger)
    # RSI Oversold/Overbought or Bollinger Band Rejection
    ltf_oversold = latest['RSI_14'] < 30 or latest['Close'] <= latest['BB_Lower']
    ltf_overbought = latest['RSI_14'] > 70 or latest['Close'] >= latest['BB_Upper']

    # Confluence
    long_signal = htf_trend_up and ltf_oversold
    short_signal = htf_trend_down and ltf_overbought

    if long_signal:
        return {"direction": "Long", "price": latest['Close'], "atr": latest['ATR_14']}
    elif short_signal:
        return {"direction": "Short", "price": latest['Close'], "atr": latest['ATR_14']}

    return None
