import sqlite3
import pandas as pd
from typing import Dict, List, Optional
from .logger import quant_logger
from .config import DB_PATH

class PaperDB:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
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
                        status TEXT NOT NULL,
                        exit_time TEXT,
                        exit_price REAL,
                        pnl REAL,
                        net_pnl REAL
                    )
                ''')
                conn.commit()
            quant_logger.info("SQLite Database initialized successfully.")
        except Exception as e:
            quant_logger.critical(f"Database initialization failed: {e}")

    def open_trade(self, trade_data: Dict) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (trade_data['ticker'], trade_data['direction'], trade_data['entry_time'],
                      trade_data['entry_price'], trade_data['sl_price'], trade_data['tp_price'],
                      trade_data['position_size'], 'Open'))
                conn.commit()
                trade_id = cursor.lastrowid
                quant_logger.info(f"Trade Open saved to DB: {trade_data['ticker']} {trade_data['direction']} (ID: {trade_id})")
                return trade_id
        except Exception as e:
            quant_logger.error(f"Failed to save open trade to DB: {e}")
            return -1

    def close_trade(self, trade_id: int, exit_time: str, exit_price: float, pnl: float, net_pnl: float):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades
                    SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?, net_pnl = ?
                    WHERE trade_id = ?
                ''', (exit_time, exit_price, pnl, net_pnl, trade_id))
                conn.commit()
                quant_logger.info(f"Trade Closed in DB: ID {trade_id} | Net PnL: {net_pnl:.2f}")
        except Exception as e:
            quant_logger.error(f"Failed to close trade in DB: {e}")

    def update_sl_price(self, trade_id: int, new_sl: float):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE trades SET sl_price = ? WHERE trade_id = ?
                ''', (new_sl, trade_id))
                conn.commit()
                quant_logger.info(f"Trailing Stop updated in DB for Trade ID {trade_id} -> New SL: {new_sl:.4f}")
        except Exception as e:
            quant_logger.error(f"Failed to update SL in DB: {e}")

    def get_open_positions(self) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            quant_logger.error(f"Failed to fetch open positions: {e}")
            return []

    def get_all_closed_trades_df(self) -> pd.DataFrame:
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed'", conn)
                return df
        except Exception as e:
            quant_logger.error(f"Failed to fetch closed trades as DF: {e}")
            return pd.DataFrame()
