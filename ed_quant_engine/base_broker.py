from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseBroker(ABC):
    """Abstract Base Class (ABC) defining the mandatory interface for any Broker Integration (Paper, Binance, IBKR)."""

    @abstractmethod
    def get_account_balance(self) -> float:
        """Returns current available account balance."""
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Retrieves currently open positions."""
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float) -> Dict[str, Any]:
        """Executes a market order and returns an Execution Receipt."""
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: str, new_sl: float) -> bool:
        """Updates the Stop Loss level for an open position."""
        pass

    @abstractmethod
    def close_position(self, trade_id: str, current_price: float) -> Dict[str, Any]:
        """Closes an open position at market price and calculates PnL."""
        pass
