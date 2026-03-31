import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from features import add_features
from logger import setup_logger

logger = setup_logger("StrategyEngine")

def generate_signals(df: pd.DataFrame, ticker: str, atr_multiplier: float = 1.5, tp_multiplier: float = 3.0) -> Optional[Dict[str, Any]]:
    """
    Phase 4: Generates MTF confluence signals based strictly on closed candles to avoid lookahead bias.
    """
    if df.empty or len(df) < 200:
        return None

    # We strictly look at the previous, fully closed candle (iloc[-1] in our merged df context)
    # The dataframe should already have features added from MTF pipeline
    last_closed = df.iloc[-1]

    # Required exact column names from pandas_ta
    required_cols = ['Close', 'EMA_50', 'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'BBL_20_2.0_2.0', 'BBU_20_2.0_2.0']
    for col in required_cols:
        if col not in last_closed:
            return None

    close = last_closed['Close']
    ema50 = last_closed['EMA_50']
    rsi = last_closed['RSI_14']
    macd_hist = last_closed['MACDh_12_26_9']
    atr = last_closed['ATRr_14']
    bb_lower = last_closed['BBL_20_2.0_2.0']
    bb_upper = last_closed['BBU_20_2.0_2.0']

    signal = None

    # Long Confluence: Trend UP, RSI oversold or bouncing off lower BB, MACD momentum positive
    if close > ema50 and (rsi < 35 or close <= bb_lower) and macd_hist > 0:
        signal = "Long"
        sl = close - (atr_multiplier * atr)
        tp = close + (tp_multiplier * atr)

    # Short Confluence: Trend DOWN, RSI overbought or bouncing off upper BB, MACD momentum negative
    elif close < ema50 and (rsi > 65 or close >= bb_upper) and macd_hist < 0:
        signal = "Short"
        sl = close + (atr_multiplier * atr)
        tp = close - (tp_multiplier * atr)

    if signal:
        logger.info(f"Sinyal Üretildi [{ticker}]: {signal} @ {close:.4f} | SL: {sl:.4f} TP: {tp:.4f}")
        return {
            "ticker": ticker,
            "direction": signal,
            "entry_price": close,
            "sl_price": sl,
            "tp_price": tp,
            "atr": atr
        }
    return None

def update_trailing_stop(current_price: float, current_sl: float, direction: str, atr: float) -> Optional[float]:
    """
    Phase 12: Strictly monotonic ATR-based trailing stop calculation.
    Stop can only move in the direction of profit.
    """
    new_sl = None
    if direction == 'Long':
        calculated_sl = current_price - (1.5 * atr)
        if calculated_sl > current_sl: # Only move UP
            new_sl = calculated_sl
    elif direction == 'Short':
        calculated_sl = current_price + (1.5 * atr)
        if calculated_sl < current_sl: # Only move DOWN
            new_sl = calculated_sl

    return new_sl
