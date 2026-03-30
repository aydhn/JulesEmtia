import datetime
from abc import ABC, abstractmethod
from core.paper_db import PaperDB
from core.logger import get_logger

logger = get_logger()

class BaseBroker(ABC):
    """Abstract Base Class for Broker Abstraction Layer (SOLID Compliance)."""
    @abstractmethod
    def place_order(self, ticker: str, direction: str, size: float, price: float, sl: float, tp: float, cost: float):
        pass

    @abstractmethod
    def close_order(self, trade_id: int, current_price: float):
        pass

    @abstractmethod
    def modify_stop_loss(self, trade_id: int, new_sl: float):
        pass

class PaperBroker(BaseBroker):
    """Local SQLite-based execution handler for Paper Trading."""
    def __init__(self, db: PaperDB):
        self.db = db

    def place_order(self, ticker: str, direction: str, size: float, price: float, sl: float, tp: float, cost: float):
        query = """INSERT INTO trades (ticker, direction, entry_price, sl_price, tp_price, position_size, status, cost)
                   VALUES (?, ?, ?, ?, ?, ?, 'Open', ?)"""
        trade_id = self.db.execute(query, (ticker, direction, price, sl, tp, size, cost))
        logger.info(f"FİŞ KESİLDİ: [{trade_id}] {ticker} {direction} Lot: {size:.2f} | Entry: {price:.4f} | SL: {sl:.4f}")
        return trade_id

    def close_order(self, trade_id: int, current_price: float):
        trade_tuple = self.db.fetch_all("SELECT direction, entry_price, position_size, cost FROM trades WHERE trade_id = ?", (trade_id,))
        if not trade_tuple: return

        direction, entry_price, size, initial_cost = trade_tuple[0]

        # PnL Calculation
        if direction == "Long":
            gross_pnl = (current_price - entry_price) * size
        else: # Short
            gross_pnl = (entry_price - current_price) * size

        # Deduct initial slippage cost and exit slippage cost (Assume exit cost == entry cost)
        net_pnl = gross_pnl - (initial_cost * size * 2)

        query = "UPDATE trades SET status = 'Closed', exit_price = ?, pnl = ? WHERE trade_id = ?"
        self.db.execute(query, (current_price, net_pnl, trade_id))

        icon = "🟢" if net_pnl > 0 else "🔴"
        logger.info(f"{icon} İŞLEM KAPANDI [{trade_id}]: Fiyat {current_price:.4f} | Net PnL: ${net_pnl:.2f}")

    def modify_stop_loss(self, trade_id: int, new_sl: float):
        query = "UPDATE trades SET sl_price = ? WHERE trade_id = ?"
        self.db.execute(query, (new_sl, trade_id))
        logger.debug(f"SL GÜNCELLENDİ: [{trade_id}] Yeni SL: {new_sl:.4f}")
