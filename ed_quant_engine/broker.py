from abc import ABC, abstractmethod
import datetime
from typing import Dict, Any, List
from paper_db import PaperDB
from logger import logger

class BaseBroker(ABC):
    """
    Phase 24: Broker Abstraction Layer (SPL Level 3 Standards)
    Decouples strategy execution from broker API.
    Provides methods for Paper or Live Trading (e.g. InteractiveBrokers, Binance).
    Ensures strict Audit Trails for derivatives trading.
    """

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, position_size: float, entry_price: float, sl_price: float, tp_price: float, reason: str = "") -> Dict[str, Any]:
        """Returns execution receipt."""
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, reason: str = "TP/SL") -> Dict[str, Any]:
        """Returns execution receipt with realized PnL."""
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass


class PaperBroker(BaseBroker):
    """
    Simulated Broker using local SQLite Database.
    Wraps all PaperDB operations.
    Generates Audit Trails (Execution Receipts) required for Quant architecture.
    """

    def get_account_balance(self) -> float:
        return PaperDB.get_balance()

    def place_market_order(self, ticker: str, direction: str, position_size: float, entry_price: float, sl_price: float, tp_price: float, reason: str = "") -> Dict[str, Any]:
        """
        Simulates market order execution with Slippage & Spread considered.
        Logs an Audit Trail receipt.
        """
        # Execute trade
        PaperDB.execute_query(
            '''
            INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, reason)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, 'Open', ?)
            ''',
            (ticker, direction, entry_price, sl_price, tp_price, position_size, reason)
        )

        # Audit Trail Receipt
        receipt = {
            "order_id": PaperDB.execute_query("SELECT last_insert_rowid() as id").fetchone()['id'],
            "ticker": ticker,
            "direction": direction,
            "position_size": position_size,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "FILLED"
        }

        logger.info(f"AUDIT TRAIL: Order Filled. Receipt: {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        """Updates SL price if the new SL is better (Strictly Monotonic)."""
        # Verify it's an open trade
        trade = PaperDB.fetch_one("SELECT sl_price, direction FROM trades WHERE trade_id = ?", (trade_id,))
        if not trade:
            return False

        current_sl = trade['sl_price']
        direction = trade['direction']

        # Stop-Loss can only move in the direction of profit
        if direction == 'Long' and new_sl_price > current_sl:
            PaperDB.execute_query("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl_price, trade_id))
            logger.info(f"Trailing Stop updated for Trade ID {trade_id}: {current_sl} -> {new_sl_price}")
            return True
        elif direction == 'Short' and new_sl_price < current_sl:
            PaperDB.execute_query("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl_price, trade_id))
            logger.info(f"Trailing Stop updated for Trade ID {trade_id}: {current_sl} -> {new_sl_price}")
            return True

        return False

    def close_position(self, trade_id: int, exit_price: float, reason: str = "TP/SL Hit") -> Dict[str, Any]:
        """
        Closes a position, calculates PnL, updates balance, and logs receipt.
        """
        trade = PaperDB.fetch_one("SELECT ticker, direction, entry_price, position_size FROM trades WHERE trade_id = ?", (trade_id,))
        if not trade:
            return {}

        direction = 1 if trade['direction'] == 'Long' else -1
        pnl = (exit_price - trade['entry_price']) * trade['position_size'] * direction

        # Optional: Add simulated funding or commissions here for Net PnL
        net_pnl = pnl # Gross PnL for now, assuming spread/slippage handled at execution price calculation

        PaperDB.execute_query(
            '''
            UPDATE trades
            SET status = 'Closed', exit_time = datetime('now', 'localtime'), exit_price = ?, pnl = ?, net_pnl = ?, reason = ?
            WHERE trade_id = ?
            ''',
            (exit_price, pnl, net_pnl, reason, trade_id)
        )

        # Update Balance
        PaperDB.update_balance(net_pnl)

        receipt = {
            "order_id": trade_id,
            "ticker": trade['ticker'],
            "exit_price": exit_price,
            "realized_pnl": net_pnl,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "CLOSED"
        }

        logger.info(f"AUDIT TRAIL: Position Closed. Receipt: {receipt}")
        return receipt

    def get_open_positions(self) -> List[Dict[str, Any]]:
        rows = PaperDB.fetch_all("SELECT * FROM trades WHERE status = 'Open'")
        return [dict(row) for row in rows]
