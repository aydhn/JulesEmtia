import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from features import add_features
from logger import setup_logger

logger = setup_logger("StrategyEngine")

def generate_signals(df: pd.DataFrame, ticker: str, atr_multiplier: float = 1.5, tp_multiplier: float = 3.0) -> Optional[Dict[str, Any]]:
    """Generates signals based strictly on closed candles to avoid lookahead bias."""
    if df.empty or len(df) < 200:
        return None

    df = add_features(df)

    # We strictly look at the previous, fully closed candle (iloc[-1])
    # The current forming candle is iloc[-1] if not resampled properly, but assuming data is up to close.
    last_closed = df.iloc[-1]

    # Extract values safely
    close = last_closed['Close']
    ema50 = last_closed['EMA_50']
    rsi = last_closed['RSI_14']
    macd_hist = last_closed['MACDh_12_26_9']
    atr = last_closed['ATRr_14']
    bb_lower = last_closed['BBL_20_2.0']
    bb_upper = last_closed['BBU_20_2.0']

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
