from logger import get_logger
from config import FRACTIONAL_KELLY, MAX_LOT_CAP_PCT
import pandas as pd

log = get_logger()

def calculate_kelly_fraction(closed_trades_df: pd.DataFrame, max_cap: float = MAX_LOT_CAP_PCT, multiplier: float = FRACTIONAL_KELLY) -> float:
    """
    Calculates dynamic position sizing using Fractional Kelly Criterion.
    f* = (bp - q) / b
    where p = win rate, q = loss rate, b = avg win / avg loss.
    """
    if closed_trades_df is None or len(closed_trades_df) < 10:
        log.info("Not enough trade history for Kelly. Using default 1% risk.")
        return 0.01

    wins = closed_trades_df[closed_trades_df['pnl'] > 0]
    losses = closed_trades_df[closed_trades_df['pnl'] <= 0]

    if len(wins) == 0 or len(losses) == 0:
        return 0.01

    p = len(wins) / len(closed_trades_df)
    q = 1.0 - p

    avg_win = wins['pnl'].mean()
    avg_loss = abs(losses['pnl'].mean())

    if avg_loss == 0: return 0.01

    b = avg_win / avg_loss

    f_star = (b * p - q) / b

    # JP Morgan Safety Filter
    fractional_f = f_star * multiplier

    # Hard Cap Limit
    final_risk_pct = min(max(fractional_f, 0.005), max_cap) # Floor 0.5%, Ceiling 4%

    log.info(f"Kelly Calc: p={p:.2f}, b={b:.2f}, f*={f_star:.3f} -> Final Risk: {final_risk_pct:.3%}")
    return final_risk_pct

def trailing_stop_logic(direction: str, current_price: float, entry_price: float, current_sl: float, atr: float, risk_free_multiplier: float = 1.0) -> float:
    """
    Strictly Monotonic Trailing Stop & Breakeven logic.
    Stop-Loss only moves in the direction of profit. Never backwards.
    """
    new_sl = current_sl

    # 1. Breakeven logic
    if direction == "Long" and current_price >= entry_price + (atr * risk_free_multiplier):
        if current_sl < entry_price:
            new_sl = entry_price # Move to Breakeven

    elif direction == "Short" and current_price <= entry_price - (atr * risk_free_multiplier):
        if current_sl > entry_price:
            new_sl = entry_price # Move to Breakeven

    # 2. Dynamic Trailing (Zirve - 1.5 ATR)
    if direction == "Long":
        potential_sl = current_price - (1.5 * atr)
        if potential_sl > new_sl: # STRICTLY MONOTONIC: Only move UP
            new_sl = potential_sl

    elif direction == "Short":
        potential_sl = current_price + (1.5 * atr)
        if potential_sl < new_sl and new_sl > 0: # STRICTLY MONOTONIC: Only move DOWN
            new_sl = potential_sl

    return new_sl
