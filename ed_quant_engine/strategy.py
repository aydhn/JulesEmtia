import pandas as pd
import numpy as np
from logger import logger
from portfolio_manager import portfolio_manager
from ml_validator import ml_validator
from sentiment_filter import sentiment_filter
from execution_model import get_execution_price

def generate_signals(df: pd.DataFrame, ticker: str, current_balance: float, open_positions: list, corr_matrix: pd.DataFrame, recent_trades: list) -> dict:
    '''
    Phase 4: Confluence Signal Generation & Risk Management
    Phase 16: MTF Confluence Check
    '''
    if df.empty or len(df) < 200:
        return None

    # MUST evaluate using the *last closed candle* (iloc[-1])
    # The `features.py` or `data_loader.py` MUST have handled `.shift(1)` logic.
    last_row = df.iloc[-1]

    # 1. Extract values safely
    close = last_row.get('Close', 0)
    ema_50 = last_row.get('EMA_50', 0)
    ema_200 = last_row.get('EMA_200', 0)
    rsi = last_row.get('RSI_14', 50)
    macd = last_row.get('MACD', 0)
    macd_sig = last_row.get('MACD_signal', 0)
    bb_lower = last_row.get('BB_lower', 0)
    bb_upper = last_row.get('BB_upper', 0)
    atr = last_row.get('ATR_14', 0)

    # Daily features (HTF)
    close_1d = last_row.get('Close_1d', 0)
    ema_50_1d = last_row.get('EMA_50_1d', 0)
    macd_1d = last_row.get('MACD_1d', 0)

    # Calculate average ATR for execution model
    avg_atr = df['ATR_14'].rolling(50).mean().iloc[-1] if 'ATR_14' in df.columns else atr

    direction = None

    # 2. MTF Confluence Rules (Phase 16)
    # Long Condition: Daily trend up AND Hourly oversold/momentum up
    if close_1d > ema_50_1d and macd_1d > 0: # HTF Filter
        if close > ema_50 and (rsi < 30 or close <= bb_lower) and macd > macd_sig: # LTF Trigger
            direction = "Long"

    # Short Condition: Daily trend down AND Hourly overbought/momentum down
    elif close_1d < ema_50_1d and macd_1d < 0: # HTF Filter
        if close < ema_50 and (rsi > 70 or close >= bb_upper) and macd < macd_sig: # LTF Trigger
            direction = "Short"

    if not direction:
        return None

    # 3. Validation Layers (Phase 11, 18, 20)
    if portfolio_manager.correlation_veto(ticker, direction, open_positions, corr_matrix):
        return None

    if not ml_validator.validate_signal(df, direction):
        return None

    if sentiment_filter.veto_signal(ticker, direction):
        return None

    # 4. Realistic Execution Price (Phase 21)
    entry_price = get_execution_price(ticker, close, direction, atr, avg_atr)

    # 5. Risk Management: Dynamic TP/SL (Phase 4)
    # SL = 1.5 ATR, TP = 3.0 ATR
    if direction == "Long":
        sl_price = entry_price - (1.5 * atr)
        tp_price = entry_price + (3.0 * atr)
    else:
        sl_price = entry_price + (1.5 * atr)
        tp_price = entry_price - (3.0 * atr)

    # 6. Position Sizing via Kelly (Phase 15)
    size = portfolio_manager.calculate_position_size(current_balance, entry_price, sl_price, recent_trades)

    if size <= 0:
        logger.warning(f"Zero position size calculated for {ticker}. Trade skipped.")
        return None

    logger.info(f"Signal Generated: {direction} {ticker} @ {entry_price:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f} | Size: {size:.4f}")

    return {
        "ticker": ticker,
        "direction": direction,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "size": size,
        "atr": atr
    }