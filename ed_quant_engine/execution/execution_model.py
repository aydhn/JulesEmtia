import numpy as np
from core.logger import get_logger

logger = get_logger()

class ExecutionSimulator:
    def __init__(self):
        self.spreads = {
            "Metals": 0.0002,   # 0.02%
            "Energy": 0.0003,   # 0.03%
            "Agriculture": 0.0005, # 0.05%
            "Forex_TRY": 0.0010    # 0.10% exotic spread
        }

    def get_execution_price_and_cost(self, category: str, market_price: float, current_atr: float, direction: str) -> tuple:
        """Calculates realistic Entry Price considering Spread and dynamic ATR-based Slippage."""
        base_spread = self.spreads.get(category, 0.0005)

        # Volatility penalty (Higher ATR = Wider Spread/Slippage)
        # Assuming avg ATR is 1% of price, if it spikes, slippage doubles.
        volatility_penalty = current_atr / (market_price * 0.01) if market_price > 0 else 1.0
        dynamic_slippage = base_spread * max(1.0, volatility_penalty)

        cost_impact = market_price * (dynamic_slippage / 2)

        if direction == "Long":
            executed_price = market_price + cost_impact
        else:
            executed_price = market_price - cost_impact

        logger.debug(f"Execution Model: Piyasa {market_price:.4f} | Gerçekleşen {executed_price:.4f} (Makas: %{dynamic_slippage*100:.2f})")
        return executed_price, cost_impact
