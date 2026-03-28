import pandas as pd
from config import SPREADS

def calculate_dynamic_slippage(ticker: str, atr: float, price: float, rolling_atr: float = None) -> float:
    """
    Simulates real-world friction.
    Base Spread + ATR-adjusted slippage.
    If current ATR is much higher than 50-day average ATR, slippage doubles.
    """
    category = "Forex_TRY"
    for cat, tcks in SPREADS.items():
        if ticker in tcks: category = cat

    base_spread = SPREADS.get(category, 0.0005)

    # Calculate dollar value of spread
    spread_cost = price * base_spread

    # ATR Volatility Multiplier
    slippage_multiplier = 1.0
    if rolling_atr and rolling_atr > 0:
        if atr > (rolling_atr * 1.5): # Volatility spike
            slippage_multiplier = 2.0

    total_cost_per_unit = (spread_cost / 2.0) + (atr * 0.01 * slippage_multiplier)
    return total_cost_per_unit

def apply_execution_costs(direction: str, raw_price: float, slippage: float) -> float:
    """Returns the WORSE price. You always buy higher and sell lower."""
    if direction == "Long":
        return raw_price + slippage
    elif direction == "Short":
        return raw_price - slippage
    return raw_price
