from abc import ABC, abstractmethod
from typing import Dict, Any, List
from paper_db import open_trade, close_trade, update_sl_price, get_open_positions
from logger import get_logger

log = get_logger()

class BaseBroker(ABC):
    """
    Abstract Base Class (ABC) for Execution Abstraction Layer.
    Forces all derived classes (PaperBroker, BinanceBroker, etc.) to implement these methods.
    """

    @abstractmethod
    def get_account_balance(self) -> float: pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, qty: float, price: float, sl: float, tp: float, slippage_cost: float) -> Dict[str, Any]: pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool: pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, exit_time: str, pnl: float) -> bool: pass

    @abstractmethod
    def get_open_trades(self) -> List[tuple]: pass

class PaperBroker(BaseBroker):
    """
    SQLite-backed Paper Broker simulating a live execution environment.
    All main loop interactions go through this class, making it completely
    decoupled from paper_db internals.
    """

    def __init__(self, initial_balance=10000.0):
        self.virtual_balance = initial_balance

    def get_account_balance(self) -> float:
        return self.virtual_balance

    def update_balance(self, pnl: float):
        self.virtual_balance += pnl
        log.info(f"Balance Updated: {self.virtual_balance:.2f} (PnL: {pnl:.2f})")

    def place_market_order(self, ticker: str, direction: str, qty: float, price: float, sl: float, tp: float, slippage_cost: float, time: str) -> Dict[str, Any]:
        """
        Executes a virtual market order. Calculates total exposure and logs an Audit Trail.
        """
        trade_id = open_trade(ticker, direction, time, price, sl, tp, qty, slippage_cost)
        receipt = {
            "trade_id": trade_id,
            "ticker": ticker,
            "direction": direction,
            "executed_price": price,
            "qty": qty,
            "sl": sl,
            "tp": tp,
            "slippage_cost": slippage_cost,
            "timestamp": time,
            "audit_trail": "PaperBroker Execution - V1"
        }
        log.info(f"EXECUTION RECEIPT: {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        update_sl_price(trade_id, new_sl)
        return True

    def close_position(self, trade_id: int, exit_price: float, exit_time: str, pnl: float) -> bool:
        close_trade(trade_id, exit_time, exit_price, pnl)
        self.update_balance(pnl)
        return True

    def get_open_trades(self) -> List[tuple]:
        return get_open_positions()
