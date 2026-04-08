import pandas as pd
from src.logger import get_logger
from src.portfolio import calculate_fractional_kelly
from src.config import get_spread

logger = get_logger()

def generate_signals(df: pd.DataFrame, ticker: str, current_balance: float, macro_regime: str = "Risk-On"):
    """
    Confluence Signal Generation with MTF veto, multiple sub-strategies and Macro Regime veto.
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

    # Helper to find auto-generated column names
    macd_h = [c for c in df.columns if c.startswith('MACDh')]
    macd_val = last_row[macd_h[0]] if macd_h else 0

    stochrsi_k_cols = [c for c in df.columns if c.startswith('STOCHRSIk')]
    stochrsi_k = last_row[stochrsi_k_cols[0]] if stochrsi_k_cols else 50
    stochrsi_d_cols = [c for c in df.columns if c.startswith('STOCHRSId')]
    stochrsi_d = last_row[stochrsi_d_cols[0]] if stochrsi_d_cols else 50

    bb_l = [c for c in df.columns if c.startswith('BBL_')]
    bb_lower = last_row[bb_l[0]] if bb_l else 0
    bb_u = [c for c in df.columns if c.startswith('BBU_')]
    bb_upper = last_row[bb_u[0]] if bb_u else 0

    adx_cols = [c for c in df.columns if c.startswith('ADX_')]
    adx_val = last_row[adx_cols[0]] if adx_cols else 0

    # MTF HTF Check (Daily Trend Veto)
    htf_ema50 = last_row.get('HTF_EMA_50', 0)
    htf_close = last_row.get('HTF_Close', 0)
    htf_trend_up = htf_close > htf_ema50 if htf_ema50 else True
    htf_trend_down = htf_close < htf_ema50 if htf_ema50 else True

    signal = None

    # SUB-STRATEGY 1: Trend Following (ADX + EMA)
    trend_long = (
        last_row['Close'] > last_row['EMA_50'] and
        adx_val > 25 and
        macd_val > 0 and
        htf_trend_up
    )

    trend_short = (
        last_row['Close'] < last_row['EMA_50'] and
        adx_val > 25 and
        macd_val < 0 and
        htf_trend_down
    )

    # SUB-STRATEGY 2: Mean Reversion / Divergence
    div_long = (
        (last_row.get('Bull_Div', 0) == 1 or last_row.get('MACD_Bull_Div', 0) == 1) and
        stochrsi_k < 30 and stochrsi_k > stochrsi_d and
        htf_trend_up
    )

    div_short = (
        (last_row.get('Bear_Div', 0) == 1 or last_row.get('MACD_Bear_Div', 0) == 1) and
        stochrsi_k > 70 and stochrsi_k < stochrsi_d and
        htf_trend_down
    )

    # SUB-STRATEGY 3: Momentum Breakout (Bollinger Bands + RSI)
    mom_long = (
        last_row['Close'] > bb_upper and
        last_row['RSI_14'] > 60 and
        htf_trend_up
    )

    mom_short = (
        last_row['Close'] < bb_lower and
        last_row['RSI_14'] < 40 and
        htf_trend_down
    )

    is_long = trend_long or div_long or mom_long
    is_short = trend_short or div_short or mom_short

    # Macro Regime Veto is applied in main.py before calling this, but we can also double check or let main.py handle it.
    # main.py uses check_macro_regime_veto which evaluates the ticker and direction.

    if is_long and not is_short:
        sl_price = current_price - (1.5 * atr)
        tp_price = current_price + (3.0 * atr)
        signal = "Long"

    if is_short and not is_long:
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

def manage_open_positions(broker, df_dict: dict, black_swan: bool = False):
    """
    Evaluates open positions for Trailing Stop or Breakeven logic.
    Executes actual stops via broker.close_position if hit.
    If black_swan is True, applies aggressive trailing stops.
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

        # Determine trailing aggressiveness
        trailing_multiplier = 0.5 if black_swan else 1.5
        breakeven_trigger_multiplier = 0.5 if black_swan else 1.0

        # Check Stop Loss / Take Profit Hit
        if direction == "Long":
            if current_price <= sl_price or current_price >= tp_price:
                broker.close_position(trade_id, current_price, slippage=0.0005, spread=spread)
                continue

            # Trailing Stop & Breakeven Logic
            if current_price >= entry_price + (breakeven_trigger_multiplier * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info(f"🔒 Breakeven set for {ticker} Long")
            elif is_breakeven or black_swan:
                new_sl = current_price - (trailing_multiplier * atr)
                if new_sl > sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)

        elif direction == "Short":
            if current_price >= sl_price or current_price <= tp_price:
                broker.close_position(trade_id, current_price, slippage=0.0005, spread=spread)
                continue

            # Trailing Stop & Breakeven Logic
            if current_price <= entry_price - (breakeven_trigger_multiplier * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info(f"🔒 Breakeven set for {ticker} Short")
            elif is_breakeven or black_swan:
                new_sl = current_price + (trailing_multiplier * atr)
                if new_sl < sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)
