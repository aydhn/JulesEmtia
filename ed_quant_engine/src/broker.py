from abc import ABC, abstractmethod
from typing import Dict, Any, List
from src.paper_db import open_trade, close_trade, update_sl_price, get_open_trades

class BaseBroker(ABC):
    """Abstract Base Class defining the contract for executing trades.
    Allows plug-and-play swapping between Paper Trading and Real Brokers."""

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, lot_size: float, comment: str = "") -> Dict[str, Any]:
        """Places an order and returns a standardized Execution Receipt."""
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, pnl: float, comment: str = "") -> bool:
        pass

    @abstractmethod
    def modify_stop_loss(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass


class PaperBroker(BaseBroker):
    """Local SQLite-backed implementation of the Broker interface."""

    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance

    def get_account_balance(self) -> float:
        """Calculates current balance by adding closed PNLs to initial balance."""
        import sqlite3
        import os
        from src.paper_db import DB_PATH

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'Closed'")
            total_pnl = cursor.fetchone()[0]
            conn.close()
            return self.initial_balance + (total_pnl if total_pnl else 0.0)
        except Exception:
            return self.initial_balance

    def place_market_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, lot_size: float, comment: str = "") -> Dict[str, Any]:
        """Executes a virtual market order via the local database."""
        # Note: Slippage and Spread should already be baked into 'price' by the execution_model.
        trade_id = open_trade(ticker, direction, price, sl, tp, lot_size, comment)

        receipt = {
            "status": "FILLED",
            "trade_id": trade_id,
            "ticker": ticker,
            "direction": direction,
            "filled_price": price,
            "lot_size": lot_size,
            "timestamp": "now" # In reality fetched from DB
        }
        return receipt

    def close_position(self, trade_id: int, exit_price: float, pnl: float, comment: str = "") -> bool:
        return close_trade(trade_id, exit_price, pnl, comment)

    def modify_stop_loss(self, trade_id: int, new_sl: float) -> bool:
        return update_sl_price(trade_id, new_sl)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return get_open_trades()
