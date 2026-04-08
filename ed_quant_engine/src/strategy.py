import pandas as pd
from src.logger import get_logger
from src.portfolio import calculate_fractional_kelly
from src.config import get_spread

logger = get_logger()

def generate_signals(df: pd.DataFrame, ticker: str, current_balance: float):
    """
    Confluence Signal Generation with MTF veto.
    Uses shift(1) to ensure we only look at CLOSED candles.
    Returns a dict with trade details if a signal is found, else None.
    """
    if df.empty or len(df) < 2:
        return None

    # Get the last CLOSED candle
    last_row = df.iloc[-2]
    current_row = df.iloc[-1]

    current_price = current_row['Close']

    # Dynamic ATR for Stop Loss and Position Sizing
    atr = last_row.get('ATR_14', current_price * 0.01)

    # Helper to find auto-generated MACD column names
    macd_h = [c for c in df.columns if c.startswith('MACDh')]
    macd_val = last_row[macd_h[0]] if macd_h else 0

    bb_l = [c for c in df.columns if c.startswith('BBL_')]
    bb_lower = last_row[bb_l[0]] if bb_l else 0

    # MTF HTF Check (Daily Trend Veto)
    # If HTF columns exist (from MTF merge), enforce trend.
    htf_ema50 = last_row.get('HTF_EMA_50', 0)
    htf_close = last_row.get('HTF_Close', 0)
    htf_trend_up = htf_close > htf_ema50 if htf_ema50 else True
    htf_trend_down = htf_close < htf_ema50 if htf_ema50 else True

    signal = None

    # LONG CONDITIONS
    # 1. Price > EMA 50
    # 2. RSI crossed above 30 OR Price touched Lower BB
    # 3. MACD Histogram positive
    # 4. HTF Trend Up
    is_long = (
        last_row['Close'] > last_row['EMA_50'] and
        (last_row['RSI_14'] < 40 or last_row['Close'] <= bb_lower) and
        macd_val > 0 and
        htf_trend_up
    )

    if is_long:
        sl_price = current_price - (1.5 * atr)
        tp_price = current_price + (3.0 * atr)
        signal = "Long"

    # SHORT CONDITIONS
    is_short = (
        last_row['Close'] < last_row['EMA_50'] and
        last_row['RSI_14'] > 60 and
        macd_val < 0 and
        htf_trend_down
    )

    if is_short and signal is None:
        sl_price = current_price + (1.5 * atr)
        tp_price = current_price - (3.0 * atr)
        signal = "Short"

    if signal:
        # Calculate Position Size using Fractional Kelly
        risk_pct = calculate_fractional_kelly()
        risk_amount = current_balance * risk_pct
        sl_distance = abs(current_price - sl_price)

        position_size = risk_amount / sl_distance if sl_distance > 0 else 0

        return {
            "ticker": ticker,
            "direction": signal,
            "entry_price": current_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "position_size": position_size,
            "features": last_row
        }

    return None

def manage_open_positions(broker, df_dict: dict):
    """
    Evaluates open positions for Trailing Stop or Breakeven logic.
    Executes actual stops via broker.close_position if hit.
    """
    open_trades = broker.get_open_positions()
    for trade in open_trades:
        ticker = trade['ticker']
        if ticker not in df_dict:
            continue

        df = df_dict[ticker]
        if df.empty:
            continue

        current_price = df['Close'].iloc[-1]
        trade_id = trade['trade_id']
        direction = trade['direction']
        entry_price = trade['entry_price']
        sl_price = trade['sl_price']
        tp_price = trade['tp_price']
        is_breakeven = trade['is_breakeven']

        atr = df['ATR_14'].iloc[-2] if 'ATR_14' in df.columns else current_price * 0.01
        spread = get_spread(ticker)

        # Check Stop Loss / Take Profit Hit
        if direction == "Long":
            if current_price <= sl_price or current_price >= tp_price:
                broker.close_position(trade_id, current_price, slippage=0.0005, spread=spread)
                continue

            # Trailing Stop & Breakeven Logic
            if current_price >= entry_price + (1.0 * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info(f"🔒 Breakeven set for {ticker} Long")
            elif is_breakeven:
                new_sl = current_price - (1.5 * atr)
                if new_sl > sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)

        elif direction == "Short":
            if current_price >= sl_price or current_price <= tp_price:
                broker.close_position(trade_id, current_price, slippage=0.0005, spread=spread)
                continue

            # Trailing Stop & Breakeven Logic
            if current_price <= entry_price - (1.0 * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info(f"🔒 Breakeven set for {ticker} Short")
            elif is_breakeven:
                new_sl = current_price + (1.5 * atr)
                if new_sl < sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)
