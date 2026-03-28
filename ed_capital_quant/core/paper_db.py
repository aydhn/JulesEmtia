"""
ED Capital Quant Engine - Local Paper Trade Database
Lightweight SQLite structure to persist trade states.
"""
import sqlite3
import os
from .logger import logger
from .config import DB_NAME

class PaperTradeDatabase:
    def __init__(self, db_path=DB_NAME):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create trades table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_time TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        sl_price REAL NOT NULL,
                        tp_price REAL NOT NULL,
                        position_size REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'Open',
                        exit_time TEXT,
                        exit_price REAL,
                        pnl REAL
                    )
                ''')
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.critical(f"Database initialization failed: {e}")

    def open_trade(self, ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size):
        """Open a new paper trade and record it."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
                ''', (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size))
                trade_id = cursor.lastrowid
                conn.commit()
                logger.info(f"Trade Opened: {ticker} {direction} @ {entry_price} (SL: {sl_price}, TP: {tp_price}, Size: {position_size}) - ID: {trade_id}")
                return trade_id
        except sqlite3.Error as e:
            logger.error(f"Failed to open trade for {ticker}: {e}")
            return None

    def close_trade(self, trade_id, exit_time, exit_price, pnl):
        """Close an existing paper trade and calculate PnL."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades
                    SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
                    WHERE trade_id = ?
                ''', (exit_time, exit_price, pnl, trade_id))
                conn.commit()
                logger.info(f"Trade Closed: ID {trade_id} @ {exit_price} - PnL: {pnl}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to close trade ID {trade_id}: {e}")
            return False

    def get_open_trades(self):
        """Fetch all trades currently with 'Open' status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
                rows = cursor.fetchall()
                # Convert rows to dictionaries
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Failed to fetch open trades: {e}")
            return []

    def update_sl_price(self, trade_id, new_sl):
        """Dinamik izleyen stop-loss güncellemesi."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades
                    SET sl_price = ?
                    WHERE trade_id = ?
                ''', (new_sl, trade_id))
                conn.commit()
                logger.info(f"SL Updated: ID {trade_id} to {new_sl}")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to update SL for trade ID {trade_id}: {e}")
            return False

db = PaperTradeDatabase()
