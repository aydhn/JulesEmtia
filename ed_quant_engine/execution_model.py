import pandas as pd
from typing import Dict, Any, Tuple
from universe import get_base_spread
from logger import get_logger

logger = get_logger("execution_model")

def calculate_slippage(ticker: str, atr: float, avg_atr: float = None) -> float:
    """
    Calculates dynamic slippage based on volatility (ATR).
    If current ATR is significantly higher than average ATR, slippage increases.
    """
    base_spread = get_base_spread(ticker)

    # If volatility data is missing, apply a standard safe multiplier
    if atr is None or avg_atr is None or avg_atr == 0:
        return base_spread * 1.5

    volatility_ratio = atr / avg_atr

    # If volatility is high, increase slippage exponentially, else standard multiplier
    if volatility_ratio > 1.5:
        return base_spread * (volatility_ratio * 2.0)
    else:
        return base_spread * 1.5

def simulate_execution_cost(
    ticker: str,
    price: float,
    direction: str,
    atr: float,
    avg_atr: float = None
) -> Tuple[float, float, float]:
    """
    Simulates execution by adding spread and slippage.
    Returns: (executed_price, spread_cost, slippage_cost)
    """
    base_spread = get_base_spread(ticker)
    slippage = calculate_slippage(ticker, atr, avg_atr)

    spread_cost = price * (base_spread / 2.0)
    slippage_cost = price * slippage

    if direction == "Long":
        # Buying happens at Ask price (higher) + slippage
        executed_price = price + spread_cost + slippage_cost
    else:
        # Selling happens at Bid price (lower) - slippage
        executed_price = price - spread_cost - slippage_cost

    return executed_price, spread_cost, slippage_cost
