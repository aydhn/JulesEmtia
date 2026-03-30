import abc
from typing import Dict, List

class BaseBroker(abc.ABC):
    """
    Abstract Base Class (ABC) defining the standard interface for all broker integrations.
    This enables seamless switching between PaperTrading and Live brokers (Binance, Interactive Brokers, etc.)
    without rewriting the core trading engine logic.
    """

    @abc.abstractmethod
    def get_account_balance(self) -> float:
        """Returns the current available balance for trading."""
        pass

    @abc.abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float) -> Dict:
        """Executes a market order and returns an execution receipt."""
        pass

    @abc.abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        """Updates the stop-loss price for an open position."""
        pass

    @abc.abstractmethod
    def close_position(self, trade_id: int, exit_price: float) -> Dict:
        """Closes an open position at the specified market price."""
        pass

    @abc.abstractmethod
    def get_open_positions(self) -> List[Dict]:
        """Returns a list of all currently open positions."""
        pass
