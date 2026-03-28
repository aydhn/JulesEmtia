import pandas as pd
from src.core.config import get_base_spread
from src.core.logger import logger

class ExecutionModel:
    @staticmethod
    def calculate_slippage(ticker: str, current_atr: float, avg_atr: float) -> float:
        """
        Calculates dynamic slippage based on ATR (Volatility).
        High ATR = High slippage.
        """
        base_spread = get_base_spread(ticker)

        # Volatility multiplier
        multiplier = 1.0
        if avg_atr > 0 and current_atr > avg_atr * 1.5:
            multiplier = 2.0
            logger.warning(f"High Volatility Detected for {ticker}: Slippage Multiplier x{multiplier}")

        return base_spread * multiplier

    @staticmethod
    def get_execution_price(ticker: str, market_price: float, direction: str, atr: float, avg_atr: float) -> float:
        """
        Adjusts the execution price to include spread and dynamic slippage.
        """
        slippage = ExecutionModel.calculate_slippage(ticker, atr, avg_atr)
        spread = get_base_spread(ticker)

        # Add half spread + slippage to the price depending on direction
        cost = (spread / 2) + slippage

        if direction == "Long":
            execution_price = market_price + cost
        elif direction == "Short":
            execution_price = market_price - cost
        else:
            execution_price = market_price

        logger.debug(f"{ticker} {direction} Cost: {cost:.4f} | Execution Price: {execution_price:.4f}")
        return execution_price

    @staticmethod
    def calculate_net_pnl(direction: str, entry_price: float, exit_price: float, position_size: float) -> float:
        """
        Calculates net profit/loss based on execution prices.
        """
        if direction == "Long":
            return (exit_price - entry_price) * position_size
        else: # Short
            return (entry_price - exit_price) * position_size
