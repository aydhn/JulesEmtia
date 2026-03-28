import numpy as np
from core.config import SPREADS

def apply_slippage_and_spread(ticker: str, price: float, atr: float, direction: int) -> float:
    category = "FOREX_TRY"
    if "GC" in ticker or "SI" in ticker: category = "METALS"
    elif "CL" in ticker or "BZ" in ticker: category = "ENERGY"
    elif "ZW" in ticker or "ZC" in ticker: category = "AGRICULTURE"

    base_spread = SPREADS.get(category, 0.0005)
    dynamic_slippage = (atr / price) * 0.1 # Dynamic component

    total_cost_pct = base_spread / 2 + dynamic_slippage

    if direction == 1:
        return price * (1 + total_cost_pct)
    else:
        return price * (1 - total_cost_pct)
