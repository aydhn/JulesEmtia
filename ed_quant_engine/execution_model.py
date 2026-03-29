import pandas as pd
from typing import Dict, Any, Tuple
from ed_quant_engine.logger import log
from ed_quant_engine.config import DEFAULT_SLIPPAGE_PCT

def get_base_spread(ticker: str) -> float:
    """Returns base spread percentage per asset class."""
    if "TRY" in ticker:
        return 0.0010 # 0.1% forex exotic
    elif ticker in ["GC=F", "CL=F", "DX-Y.NYB"]:
        return 0.0002 # 0.02% majors
    else:
        return 0.0005 # 0.05% minors

def calculate_dynamic_slippage(ticker: str, current_price: float, current_atr: float, atr_sma: float) -> float:
    """Calculates volatility-adjusted slippage cost in absolute price terms."""
    base_slippage_pct = DEFAULT_SLIPPAGE_PCT

    # If volatility is much higher than average, slippage doubles
    if current_atr > (atr_sma * 1.5):
        base_slippage_pct *= 2.0
        log.debug(f"High Volatility detected for {ticker}, Slippage doubled to {base_slippage_pct:.2%}")

    abs_slippage = current_price * base_slippage_pct
    return abs_slippage

def simulate_execution(ticker: str, direction: str, market_price: float, current_atr: float, atr_sma: float) -> float:
    """Simulates realistic entry/exit price by adding half-spread and dynamic slippage."""
    base_spread_pct = get_base_spread(ticker)
    spread_cost = (market_price * base_spread_pct) / 2.0
    slippage_cost = calculate_dynamic_slippage(ticker, market_price, current_atr, atr_sma)

    if direction == 'Long':
        executed_price = market_price + spread_cost + slippage_cost # Buy at Ask + Slippage
    elif direction == 'Short':
        executed_price = market_price - spread_cost - slippage_cost # Sell at Bid - Slippage
    else:
        executed_price = market_price

    log.debug(f"Execution {direction} {ticker} @ {executed_price:.4f} (Market: {market_price:.4f}, Spread: {spread_cost:.4f}, Slippage: {slippage_cost:.4f})")
    return executed_price
