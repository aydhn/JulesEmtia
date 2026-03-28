"""
ED Capital Quant Engine - Signal Generation Module
High win-rate algorithmic logic combining confluence and JP Morgan risk metrics.
"""
import pandas as pd
from ..core.logger import logger
from ..core.config import RISK_PER_TRADE_PCT
from ..risk.position_sizing import calculate_position_size

def generate_signals(df: pd.DataFrame, ticker: str) -> dict:
    """Analyze the dataframe for trade signals using shifted (closed) candles to prevent lookahead bias."""
    if df.empty or len(df) < 2:
        return {}

    # Get the LAST CLOSED candle (since we already shifted the columns by 1 in add_features)
    # Actually, if we shifted them to '_prev', we can use the current row's '_prev' values.
    # The 'Close' of the current row is the current open/tick, but we only make decisions on the prev candle.
    current_row = df.iloc[-1]

    # Check if necessary columns exist
    if 'EMA_50_prev' not in current_row:
        logger.warning(f"Missing '_prev' columns in features for {ticker}. Check indicators module.")
        return {}

    # Variables for logic
    prev_close = df['Close'].iloc[-2] # The close of the candle before the current tick
    ema50 = current_row['EMA_50_prev']
    rsi = current_row['RSI_14_prev']
    macd_hist = current_row['MACDh_12_26_9_prev']
    bb_lower = current_row['BBL_20_2.0_prev']
    bb_upper = current_row['BBU_20_2.0_prev']
    atr = current_row['ATR_14_prev']

    signal = 0 # 0: None, 1: Long, -1: Short

    # 1. Long Confluence
    # Price > EMA50 AND (RSI < 30 OR Price touched Lower BB) AND MACD Histogram > 0
    if (prev_close > ema50) and ((rsi < 30) or (prev_close <= bb_lower)) and (macd_hist > 0):
        signal = 1

    # 2. Short Confluence
    # Price < EMA50 AND (RSI > 70 OR Price touched Upper BB) AND MACD Histogram < 0
    elif (prev_close < ema50) and ((rsi > 70) or (prev_close >= bb_upper)) and (macd_hist < 0):
        signal = -1

    if signal != 0:
        direction = "Long" if signal == 1 else "Short"
        entry_price = df['Close'].iloc[-1] # Enter at the current open/tick

        # JP Morgan Dynamic Risk (ATR-based SL/TP)
        if direction == "Long":
            sl_price = entry_price - (1.5 * atr)
            tp_price = entry_price + (3.0 * atr)
        else:
            sl_price = entry_price + (1.5 * atr)
            tp_price = entry_price - (3.0 * atr)

        # Calculate position size
        # Assume a standard 10k paper portfolio
        portfolio_balance = 10000.0
        risk_amount = portfolio_balance * RISK_PER_TRADE_PCT
        position_size = calculate_position_size(risk_amount, entry_price, sl_price)

        signal_data = {
            "ticker": ticker,
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "position_size": position_size,
            "atr": atr
        }

        logger.info(f"Signal Generated: {signal_data}")
        return signal_data

    return {}
