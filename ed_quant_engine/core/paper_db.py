import sqlite3
import pandas as pd
from typing import Dict, List, Optional
import ed_quant_engine.config as config
from ed_quant_engine.core.logger import logger

class PaperTradingDB:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS trades (
                        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticker TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_time TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        sl_price REAL NOT NULL,
                        tp_price REAL NOT NULL,
                        position_size REAL NOT NULL,
                        status TEXT DEFAULT 'Open',
                        exit_time TEXT,
                        exit_price REAL,
                        pnl REAL
                    )
                """)
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")

    def open_trade(self, ticker: str, direction: str, entry_time: str, entry_price: float, sl_price: float, tp_price: float, position_size: float) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
                """, (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size))
                conn.commit()
                logger.info(f"Trade Opened: {ticker} {direction} @ {entry_price}")
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to open trade: {e}")
            return -1

    def close_trade(self, trade_id: int, exit_time: str, exit_price: float, pnl: float):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trades
                    SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
                    WHERE trade_id = ?
                """, (exit_time, exit_price, pnl, trade_id))
                conn.commit()
                logger.info(f"Trade Closed: #{trade_id} @ {exit_price} | PNL: {pnl}")
        except Exception as e:
            logger.error(f"Failed to close trade #{trade_id}: {e}")

    def update_sl_price(self, trade_id: int, new_sl: float):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trades
                    SET sl_price = ?
                    WHERE trade_id = ?
                """, (new_sl, trade_id))
                conn.commit()
                logger.info(f"Trailing Stop updated for trade #{trade_id} to {new_sl}")
        except Exception as e:
            logger.error(f"Failed to update SL for trade #{trade_id}: {e}")

    def get_open_trades(self) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch open trades: {e}")
            return []

    def get_all_closed_trades(self) -> pd.DataFrame:
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM trades WHERE status = 'Closed'"
                return pd.read_sql_query(query, conn)
        except Exception as e:
            logger.error(f"Failed to fetch closed trades: {e}")
            return pd.DataFrame()

    def get_current_capital(self) -> float:
        closed_trades = self.get_all_closed_trades()
        if closed_trades.empty:
            return config.INITIAL_CAPITAL
        return config.INITIAL_CAPITAL + closed_trades['pnl'].sum()
