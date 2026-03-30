import pandas as pd
from typing import Dict, Any, Tuple
from src.logger import get_logger

logger = get_logger("strategy")

def generate_signals(df_merged: pd.DataFrame) -> Tuple[str, float, float]:
    """
    Evaluates trading rules on the aligned MTF DataFrame.
    Returns (Signal, SL_Distance, TP_Distance) if a valid signal exists, else ("", 0.0, 0.0)
    """
    if df_merged.empty or len(df_merged) < 2:
        return "", 0.0, 0.0

    # Strictly use the PREVIOUS closed candle (shift(1) logic implicitly handled if called after features)
    # The last row should represent the currently closed LTF candle, aligned with yesterday's HTF candle.
    current_row = df_merged.iloc[-1]

    # 1. High Timeframe (HTF - Daily) Trend Filter Master Veto
    htf_trend_up = current_row['Close_HTF'] > current_row['EMA_50_HTF'] and current_row['MACD_HTF'] > 0
    htf_trend_down = current_row['Close_HTF'] < current_row['EMA_50_HTF'] and current_row['MACD_HTF'] < 0

    # 2. Low Timeframe (LTF - Hourly) Entry Triggers
    ltf_oversold = current_row['RSI_14'] < 30 or current_row['Close'] <= current_row['BB_Lower']
    ltf_overbought = current_row['RSI_14'] > 70 or current_row['Close'] >= current_row['BB_Upper']

    ltf_macd_cross_up = current_row['MACD'] > current_row['MACD_Signal']
    ltf_macd_cross_down = current_row['MACD'] < current_row['MACD_Signal']

    # 3. Combine Logic (Confluence)
    signal = ""

    if htf_trend_up and ltf_oversold and ltf_macd_cross_up:
        signal = "Long"
    elif htf_trend_down and ltf_overbought and ltf_macd_cross_down:
        signal = "Short"

    # 4. Dynamic Risk (ATR based SL and TP)
    if signal:
        atr = current_row['ATR_14']
        sl_dist = atr * 1.5
        tp_dist = atr * 3.0 # 1:2 R/R ratio
        return signal, sl_dist, tp_dist

    return "", 0.0, 0.0
