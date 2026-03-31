import pandas as pd
import numpy as np
from logger import logger

class ExecutionSimulator:
    """
    Phase 21: Dynamic Spread & Slippage (Execution Modeling).
    Converts theoretical signals into realistic execution prices.
    Adds brutal realities like Bid/Ask spread and Volatility-adjusted slippage.
    """

    # Base Spread Table (Estimated percentage of price)
    SPREADS = {
        "Gold": 0.0002, "Silver": 0.0005, "Copper": 0.0008,
        "Palladium": 0.0015, "Platinum": 0.0010,
        "WTI Crude Oil": 0.0003, "Brent Crude Oil": 0.0003, "Natural Gas": 0.0015,
        "Wheat": 0.0008, "Corn": 0.0008, "Soybeans": 0.0008,
        "USD/TRY": 0.0010, "EUR/TRY": 0.0012, "GBP/TRY": 0.0015  # Exotics have wider spreads
    }

    # Default spread for unknown tickers
    DEFAULT_SPREAD = 0.0005

    @classmethod
    def get_base_spread(cls, ticker_name: str) -> float:
        """Returns the base spread percentage for a given asset."""
        for key, spread in cls.SPREADS.items():
            if key in ticker_name:
                return spread
        return cls.DEFAULT_SPREAD

    @classmethod
    def calculate_slippage(cls, current_atr: float, avg_atr_50: float) -> float:
        """
        Volatility-Based Dynamic Slippage.
        If current volatility (ATR) is 50% higher than historical average, double the slippage penalty.
        Returns slippage as a percentage.
        """
        base_slippage = 0.0001 # 0.01% base slippage

        if current_atr > avg_atr_50 * 1.5:
            logger.warning(f"High Volatility Execution Penalty! Slippage doubled. (ATR {current_atr:.4f} > {avg_atr_50 * 1.5:.4f})")
            return base_slippage * 2.0

        return base_slippage

    @classmethod
    def execute_trade_price(cls, ticker_name: str, raw_price: float, direction: int, atr_data: pd.Series) -> float:
        """
        Calculates the exact entry/exit price considering Spread + Slippage.
        direction: 1 (Buy/Long) or -1 (Sell/Short)
        """
        base_spread_pct = cls.get_base_spread(ticker_name)

        # Current ATR and Average ATR (over 50 periods)
        current_atr = atr_data.iloc[-1]
        avg_atr_50 = atr_data.rolling(window=50).mean().iloc[-1]

        # Dynamic slippage calculation
        slippage_pct = cls.calculate_slippage(current_atr, avg_atr_50)

        # Total cost factor (half the spread + full slippage)
        cost_factor = (base_spread_pct / 2.0) + slippage_pct

        if direction == 1:
            # Buying (Pay the Ask: Price + Cost)
            execution_price = raw_price * (1.0 + cost_factor)
        else:
            # Selling (Hit the Bid: Price - Cost)
            execution_price = raw_price * (1.0 - cost_factor)

        # Log the brutal reality
        cost_bps = cost_factor * 10000
        logger.debug(f"Execution Modeling [{ticker_name}]: Raw {raw_price:.4f} -> Exec {execution_price:.4f} (Cost: {cost_bps:.1f} bps)")

        return execution_price
