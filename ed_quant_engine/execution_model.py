import pandas as pd
from typing import Dict, Any

def calculate_slippage_and_spread(ticker: str, current_price: float, atr: float, direction: str, is_entry: bool = True) -> float:
    """Calculates realistic dynamic spread and slippage execution costs based on Phase 21 specifications."""
    # Define base spreads by asset class (as percentage of price)
    base_spreads = {
        "GC=F": 0.0002,      # 0.02% for Major Precious Metals
        "SI=F": 0.0004,      # 0.04% for Silver
        "CL=F": 0.0005,      # 0.05% for Oil
        "USDTRY=X": 0.0010,  # 0.10% for Exotic/EM Forex
        "EURTRY=X": 0.0012   # 0.12% for Cross Exotic
    }

    spread_pct = base_spreads.get(ticker, 0.0005) # Default 0.05% spread

    # Base Slippage Model (Assume 0.05% base slip, scaling with ATR)
    base_slippage_pct = 0.0005

    # We lack historical ATR series here for relative ATR,
    # so we'll use a simplified model where slippage increases linearly if ATR > 1% of price
    atr_pct = atr / current_price if current_price > 0 else 0
    volatility_multiplier = 1.0

    if atr_pct > 0.01:
        # High Volatility -> Wider slippage
        volatility_multiplier = atr_pct / 0.01

    dynamic_slippage_pct = base_slippage_pct * volatility_multiplier

    # Total Execution Cost (Percentage)
    total_cost_pct = (spread_pct / 2.0) + dynamic_slippage_pct

    # Calculate Executed Price
    if (direction == "Long" and is_entry) or (direction == "Short" and not is_entry):
        # We pay the offer (higher price) when buying, or covering a short
        executed_price = current_price * (1 + total_cost_pct)
    else:
        # We sell the bid (lower price) when shorting, or exiting a long
        executed_price = current_price * (1 - total_cost_pct)

    return executed_price
