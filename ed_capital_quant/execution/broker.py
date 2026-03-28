import sqlite3
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from core.logger import setup_logger
from core.config import DB_PATH

logger = setup_logger("broker")

class BaseBroker(ABC):
    """
    Abstract Base Class for Broker Abstraction Layer.
    Allows seamless switching between Paper and Live brokers.
    """
    @abstractmethod
    def get_account_balance(self) -> float: pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict]: pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float, entry_price: float) -> Optional[Dict]: pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float): pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, reason: str): pass

class PaperBroker(BaseBroker):
    """
    Simulates a broker using a local SQLite database for paper trading.
    Includes Execution Modeling (Slippage & Spread).
    """
    def __init__(self, initial_balance: float = 10000.0):
        self.db_path = DB_PATH
        self.initial_balance = initial_balance
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Transactions/Trades Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT,
                direction TEXT,
                entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                position_size REAL,
                status TEXT DEFAULT 'Open',
                exit_time TIMESTAMP,
                exit_price REAL,
                pnl REAL,
                close_reason TEXT
            )
        ''')

        # Account Info Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                balance REAL
            )
        ''')

        # Initialize account if empty
        cursor.execute("SELECT balance FROM account WHERE id=1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO account (id, balance) VALUES (1, ?)", (self.initial_balance,))

        conn.commit()
        conn.close()

    def get_account_balance(self) -> float:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM account WHERE id=1")
        balance = cursor.fetchone()[0]
        conn.close()
        return balance

    def update_balance(self, pnl: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE account SET balance = balance + ? WHERE id=1", (pnl,))
        conn.commit()
        conn.close()

    def get_open_positions(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_closed_positions(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Closed'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float, entry_price: float) -> Optional[Dict]:
        """
        SPL Level 3 Audit Trail: Places an order with simulated slippage and spread.
        """
        # Execution Modeling (Phase 21)
        # Assuming base spread and slippage are already factored into entry_price by the portfolio manager
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO trades (ticker, direction, entry_price, sl_price, tp_price, position_size)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticker, direction, entry_price, sl, tp, size))

            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()

            receipt = {
                "trade_id": trade_id,
                "ticker": ticker,
                "direction": direction,
                "size": size,
                "entry": entry_price,
                "sl": sl,
                "tp": tp
            }
            logger.info(f"Execution Receipt: {receipt}")
            return receipt

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None

    def modify_trailing_stop(self, trade_id: int, new_sl: float):
        """Strictly monotonic trailing stop update."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetch current SL and Direction
        cursor.execute("SELECT sl_price, direction FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()

        if row:
            current_sl, direction = row
            # Monotonicity check: SL can only move in the direction of profit
            if (direction == "Long" and new_sl > current_sl) or (direction == "Short" and new_sl < current_sl):
                cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
                conn.commit()
                logger.info(f"[Trade {trade_id}] Trailing Stop tightened to {new_sl:.4f}")

        conn.close()

    def close_position(self, trade_id: int, exit_price: float, reason: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT direction, entry_price, position_size FROM trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()

        if row:
            direction, entry_price, size = row

            # PnL Calculation
            if direction == "Long":
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size

            cursor.execute('''
                UPDATE trades
                SET status = 'Closed', exit_time = CURRENT_TIMESTAMP, exit_price = ?, pnl = ?, close_reason = ?
                WHERE trade_id = ?
            ''', (exit_price, pnl, reason, trade_id))

            conn.commit()
            conn.close()

            self.update_balance(pnl)
            logger.info(f"[Trade {trade_id}] Closed at {exit_price:.4f} | PnL: {pnl:.2f} | Reason: {reason}")
            return pnl

        conn.close()
        return 0.0
