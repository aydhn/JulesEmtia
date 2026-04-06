import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("ExecutionModel")

def get_base_spread(ticker: str) -> float:
    """Returns base spread as a percentage of price based on asset class."""
    if ticker in ["GC=F", "CL=F"]: # Major Commodities
        return 0.0002 # 0.02%
    elif ticker in ["SI=F", "HG=F"]: # Minor Commodities
        return 0.0005 # 0.05%
    elif "TRY=X" in ticker: # Exotic Forex
        return 0.0010 # 0.10%
    return 0.0003

def calculate_slippage_and_spread(ticker: str, current_price: float, current_atr: float) -> float:
    """
    Phase 21: Calculates dynamic execution cost combining Base Spread + ATR-adjusted Slippage.
    Returns the absolute price difference to be added/subtracted.
    """
    base_spread_pct = get_base_spread(ticker)
    spread_cost = current_price * (base_spread_pct / 2)

    # Dynamic Slippage: 5% of ATR
    slippage_cost = current_atr * 0.05

    total_cost = spread_cost + slippage_cost
    logger.debug(f"Maliyet Simülasyonu [{ticker}]: Spread={spread_cost:.4f}, Slippage={slippage_cost:.4f}, Toplam={total_cost:.4f}")

    return total_cost
