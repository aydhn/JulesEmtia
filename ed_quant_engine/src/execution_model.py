import pandas as pd
from typing import Dict
from src.logger import quant_logger as logger

class ExecutionModel:
    def __init__(self):
        # Base spreads per asset class (in percentage or absolute, here using percentage approximation)
        self.base_spreads = {
            "METALS": 0.0002,   # 0.02%
            "ENERGY": 0.0003,   # 0.03%
            "AGRI": 0.0005,     # 0.05%
            "FOREX_TRY": 0.0010 # 0.10%
        }

    def _get_category(self, ticker: str) -> str:
        # Import inside to avoid circular deps if TICKERS is used elsewhere
        from src.config import TICKERS
        for category, tickers in TICKERS.items():
            if ticker in tickers:
                return category
        return "UNKNOWN"

    def calculate_slippage(self, ticker: str, current_price: float, current_atr: float, avg_atr: float) -> float:
        """
        Calculates dynamic slippage based on volatility (ATR).
        If current ATR > avg ATR, increase slippage.
        """
        category = self._get_category(ticker)
        base_spread = self.base_spreads.get(category, 0.0005) # Default 0.05%

        # Volatility multiplier
        volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0

        # If volatility is 50% higher than average, double the slippage
        if volatility_ratio > 1.5:
             multiplier = 2.0
             logger.debug(f"High Volatility ({volatility_ratio:.2f}x) detected for {ticker}. Doubling slippage.")
        else:
             multiplier = 1.0

        # Dynamic slippage cost in price terms
        dynamic_spread = base_spread * multiplier
        slippage_cost = current_price * dynamic_spread

        return slippage_cost

    def apply_entry_costs(self, ticker: str, direction: str, market_price: float, current_atr: float, avg_atr: float) -> float:
        """
        Returns the realistic entry price (worse than market price).
        """
        slippage = self.calculate_slippage(ticker, market_price, current_atr, avg_atr)
        category = self._get_category(ticker)
        base_spread = self.base_spreads.get(category, 0.0005)

        spread_cost = market_price * (base_spread / 2) # Half spread for one side

        if direction == "Long":
            return market_price + spread_cost + slippage
        elif direction == "Short":
            return market_price - spread_cost - slippage
        return market_price

    def apply_exit_costs(self, ticker: str, direction: str, exit_price: float, current_atr: float, avg_atr: float) -> float:
        """
        Returns realistic exit price.
        """
        slippage = self.calculate_slippage(ticker, exit_price, current_atr, avg_atr)
        category = self._get_category(ticker)
        base_spread = self.base_spreads.get(category, 0.0005)

        spread_cost = exit_price * (base_spread / 2)

        # Exiting a Long means Selling
        if direction == "Long":
             return exit_price - spread_cost - slippage
        # Exiting a Short means Buying
        elif direction == "Short":
             return exit_price + spread_cost + slippage
        return exit_price

