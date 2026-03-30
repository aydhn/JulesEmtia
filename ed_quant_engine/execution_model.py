import pandas as pd
import numpy as np
from typing import Dict, Tuple

from logger import log
from data_loader import UNIVERSE

# Asset Class Base Spread Definitions (Realistic trading costs)
BASE_SPREADS = {
    "Major_Commodities": 0.0002, # 0.02%
    "Minor_Commodities": 0.0005, # 0.05%
    "TRY_Forex": 0.0010          # 0.10% (Wide spread on exotics)
}

def get_asset_class(ticker: str) -> str:
    """Helper to classify a ticker to assign realistic spreads."""
    if ticker in ["GC=F", "CL=F", "BZ=F"]:
        return "Major_Commodities"
    elif "TRY" in ticker:
        return "TRY_Forex"
    else:
        return "Minor_Commodities"

def calculate_dynamic_execution_price(ticker: str, direction: str, current_price: float, df: pd.DataFrame, atr_multiplier: float = 1.0) -> Tuple[float, float, float]:
    """
    Simulates real-world execution costs: Bid/Ask Spread + Volatility-adjusted Slippage.
    Returns: (Executed_Price, Spread_Cost, Slippage_Cost)
    """
    if df.empty or 'ATR_14' not in df.columns:
        log.warning(f"Execution Model: ATR missing for {ticker}. Using flat 0.1% cost.")
        flat_cost = current_price * 0.001
        executed_price = current_price + flat_cost if direction == "Long" else current_price - flat_cost
        return executed_price, flat_cost/2, flat_cost/2

    try:
        # Determine Base Spread
        asset_class = get_asset_class(ticker)
        base_spread = current_price * BASE_SPREADS[asset_class]

        # Dynamic Slippage (ATR adjusted)
        current_atr = df['ATR_14'].iloc[-1]
        historical_atr_mean = df['ATR_14'].mean()

        # If current volatility is 50% higher than average, slippage doubles.
        volatility_ratio = current_atr / historical_atr_mean if historical_atr_mean > 0 else 1.0
        slippage_cost = (current_atr * 0.05) * volatility_ratio * atr_multiplier # Assume 5% of ATR is normal slippage

        # Total cost is Spread + Slippage
        total_penalty = (base_spread / 2) + slippage_cost

        # Calculate Executed Price
        if direction == "Long":
            executed_price = current_price + total_penalty # You buy higher than the market
        elif direction == "Short":
            executed_price = current_price - total_penalty # You sell lower than the market
        else:
            executed_price = current_price
            total_penalty = 0

        return executed_price, (base_spread / 2), slippage_cost

    except Exception as e:
        log.error(f"Execution model failed for {ticker}: {e}. Defaulting to market price.")
        return current_price, 0.0, 0.0

