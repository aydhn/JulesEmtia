import sqlite3
import pandas as pd
from core.config import DB_NAME

class PaperDB:
    def __init__(self, db_name=DB_NAME):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_table()

    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            direction INTEGER,
            entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            entry_price REAL,
            sl_price REAL,
            tp_price REAL,
            position_size REAL,
            status TEXT DEFAULT 'OPEN',
            exit_time TIMESTAMP,
            exit_price REAL,
            pnl REAL
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def open_trade(self, ticker: str, direction: int, entry_price: float, sl: float, tp: float, size: float):
        query = "INSERT INTO trades (ticker, direction, entry_price, sl_price, tp_price, position_size) VALUES (?, ?, ?, ?, ?, ?)"
        self.conn.execute(query, (ticker, direction, entry_price, sl, tp, size))
        self.conn.commit()

    def get_open_trades(self):
        query = "SELECT * FROM trades WHERE status = 'OPEN'"
        return pd.read_sql(query, self.conn)

    def get_closed_trades(self):
        query = "SELECT * FROM trades WHERE status = 'CLOSED'"
        return pd.read_sql(query, self.conn)

    def get_all_trades(self):
        query = "SELECT * FROM trades"
        return pd.read_sql(query, self.conn)

    def update_sl(self, trade_id: int, new_sl: float):
        query = "UPDATE trades SET sl_price = ? WHERE trade_id = ?"
        self.conn.execute(query, (new_sl, trade_id))
        self.conn.commit()

    def close_trade(self, trade_id: int, exit_price: float, pnl: float):
        query = "UPDATE trades SET status = 'CLOSED', exit_time = CURRENT_TIMESTAMP, exit_price = ?, pnl = ? WHERE trade_id = ?"
        self.conn.execute(query, (exit_price, pnl, trade_id))
        self.conn.commit()

db = PaperDB()
