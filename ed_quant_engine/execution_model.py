import numpy as np
from logger import logger

def calculate_dynamic_cost(ticker: str, current_price: float, current_atr: float, avg_atr: float) -> tuple[float, float]:
    '''
    Phase 21: Dynamic Spread, Slippage & Execution Modeling
    Returns (spread_cost, slippage_cost) as absolute values.
    '''
    # 1. Base Spread Definitions
    base_spread_pct = 0.0005 # Default 0.05%

    if "TRY=X" in ticker:
        base_spread_pct = 0.0010 # 0.1% for TRY pairs
    elif ticker in ["GC=F", "CL=F", "EURUSD=X"]:
        base_spread_pct = 0.0002 # 0.02% for Highly liquid majors

    base_spread_abs = current_price * base_spread_pct

    # 2. Volatility-Based Dynamic Slippage
    slippage_multiplier = 1.0

    # If volatility is 50% higher than average, double the slippage
    if current_atr > (avg_atr * 1.5):
        slippage_multiplier = 2.0
    elif current_atr > (avg_atr * 2.0):
        slippage_multiplier = 3.0

    # Assume base slippage is half the spread
    slippage_abs = (base_spread_abs / 2) * slippage_multiplier

    logger.debug(f"[{ticker}] Execution Model - Spread: {base_spread_abs:.4f}, Slippage: {slippage_abs:.4f}")

    return base_spread_abs, slippage_abs

def get_execution_price(ticker: str, market_price: float, direction: str, current_atr: float, avg_atr: float) -> float:
    '''
    Calculates realistic entry/exit price after crossing the spread and suffering slippage.
    '''
    spread, slippage = calculate_dynamic_cost(ticker, market_price, current_atr, avg_atr)

    # Long pays ASK (higher), suffers upward slippage
    if direction == "Long":
        execution_price = market_price + (spread / 2) + slippage
    # Short sells BID (lower), suffers downward slippage
    else:
        execution_price = market_price - (spread / 2) - slippage

    return execution_price