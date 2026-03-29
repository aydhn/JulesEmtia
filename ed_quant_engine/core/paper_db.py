import sqlite3
import os

class PaperDB:
    def __init__(self, db_path="data/paper_db.sqlite3"):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, direction TEXT, entry_time TEXT, entry_price REAL,
            sl_price REAL, tp_price REAL, position_size REAL, status TEXT,
            exit_time TEXT, exit_price REAL, pnl REAL, slippage_cost REAL
        )''')
        self.conn.commit()

    def execute_query(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor.lastrowid

    def fetch_all(self, query, params=()):
        return self.conn.cursor().execute(query, params).fetchall()
