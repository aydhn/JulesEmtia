from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd

class BaseBroker(ABC):
    """Abstract Base Class for Broker Abstraction Layer (Phase 24)."""

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def place_market_order(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Places a market order and returns an execution receipt."""
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, reason: str) -> bool:
        pass

    @abstractmethod
    def calculate_slippage_and_spread(self, ticker: str, atr: float, price: float) -> float:
        """Realistic cost modeling (Phase 21)."""
        pass
