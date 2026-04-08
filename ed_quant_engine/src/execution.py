import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class ExecutionModel:
    """
    Phase 21: Dynamic Slippage and Execution Cost Modeling
    """
    def __init__(self):
        # Base spread percentages for categories
        self.base_spreads = {
            "Metals": 0.0002,  # 0.02%
            "Energy": 0.0003,  # 0.03%
            "Agri":   0.0005,  # 0.05%
            "Forex":  0.0010   # 0.10% (TRY pairs are wide)
        }

    def get_category(self, ticker: str) -> str:
        from src.config import TICKERS
        for cat, tickers in TICKERS.items():
            if ticker in tickers:
                return cat
        return "Metals"

    def calculate_costs(self, ticker: str, current_price: float, atr: float) -> Tuple[float, float]:
        """Calculates dynamic spread and ATR-adjusted slippage."""
        category = self.get_category(ticker)
        base_spread = self.base_spreads.get(category, 0.0002) * current_price

        # Volatility factor based on ATR relative to price (normalized approx 0.5%)
        volatility_factor = (atr / current_price) / 0.005
        volatility_factor = max(1.0, min(volatility_factor, 3.0)) # Cap multiplier

        slippage = (base_spread * 0.5) * volatility_factor

        return base_spread, slippage
