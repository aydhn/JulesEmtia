from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class BaseBroker(ABC):
    """
    Abstract Base Class representing the execution layer.
    Allows decoupling algorithm logic from the physical trading platform.
    """

    @abstractmethod
    def get_account_balance(self) -> float:
        """Returns the current account balance."""
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl: float, tp: float) -> Optional[Dict]:
        """Places a market order and returns an execution receipt."""
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, reason: str = "") -> bool:
        """Closes an open position."""
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        """Modifies the stop-loss order (Trailing Stop / Breakeven)."""
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict]:
        """Returns all currently open positions."""
        pass
