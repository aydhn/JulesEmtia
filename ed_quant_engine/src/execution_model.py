from typing import Tuple
from src.logger import get_logger

logger = get_logger("execution_model")

# Base Static Spreads by Asset Class (in percentage terms)
ASSET_SPREADS = {
    # Major Commodities
    "GC=F": 0.0002, "SI=F": 0.0005, "CL=F": 0.0003, "HG=F": 0.0005,
    # Minor Commodities
    "BZ=F": 0.0004, "NG=F": 0.0010, "ZC=F": 0.0015, "ZW=F": 0.0015,
    # TRY based Exotic Forex Pairs (High Spreads)
    "USDTRY=X": 0.0010, "EURTRY=X": 0.0012, "GBPTRY=X": 0.0015, "JPYTRY=X": 0.0020
}

def calculate_dynamic_slippage(ticker: str, current_price: float, current_atr: float, avg_atr: float) -> Tuple[float, float]:
    """
    Calculates dynamic spread and slippage cost based on volatility (ATR).
    Returns (dynamic_spread_cost, slippage_cost) in absolute price terms.
    """
    base_spread_pct = ASSET_SPREADS.get(ticker, 0.0005) # Default 5 bps
    base_spread_cost = current_price * base_spread_pct

    # Volatility multiplier: If current ATR is 50% higher than average, slippage doubles.
    vol_multiplier = 1.0
    if current_atr > avg_atr:
        vol_multiplier = current_atr / avg_atr

    dynamic_spread_cost = base_spread_cost * vol_multiplier

    # Slippage is assumed to be 50% of the dynamic spread as a base cost
    slippage_cost = (dynamic_spread_cost * 0.5) * vol_multiplier

    return dynamic_spread_cost, slippage_cost

def apply_execution_costs(ticker: str, direction: str, market_price: float, current_atr: float, avg_atr: float) -> float:
    """
    Applies spread and slippage to generate a realistic execution entry/exit price.
    """
    dyn_spread, slippage = calculate_dynamic_slippage(ticker, market_price, current_atr, avg_atr)

    if direction == "Long":
        # Buying is always at the Ask price (higher) + Slippage pushing price up
        executed_price = market_price + (dyn_spread / 2) + slippage
    elif direction == "Short":
        # Selling is always at the Bid price (lower) - Slippage pushing price down
        executed_price = market_price - (dyn_spread / 2) - slippage
    else:
        executed_price = market_price

    # Log execution costs for audit trail
    cost_bps = ((abs(executed_price - market_price)) / market_price) * 10000
    logger.debug(f"Execution Cost for {ticker} {direction}: {cost_bps:.2f} bps (Spread: {dyn_spread:.4f}, Slippage: {slippage:.4f})")

    return executed_price
