from abc import ABC, abstractmethod
from typing import Dict, List, Any

class BaseBroker(ABC):
    """
    Broker Abstraction Layer.
    Allows switching between Paper Trading, Binance, Interactive Brokers, etc.
    """

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, quantity: float, slippage: float) -> Dict[str, Any]:
        """
        Must return an Execution Receipt including realized slippage and commission.
        """
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: str, new_sl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def close_position(self, trade_id: str, current_price: float) -> Dict[str, Any]:
        pass
