import sqlite3
import config
from logger import logger
from datetime import datetime

class PaperDB:
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, direction TEXT, entry_time TEXT,
                entry_price REAL, sl_price REAL, tp_price REAL,
                position_size REAL, status TEXT, exit_time TEXT,
                exit_price REAL, pnl REAL
            )''')

    def get_open_trades(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM trades WHERE status = 'Open'")]

    def get_recent_trades(self, limit=50):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM trades WHERE status = 'Closed' ORDER BY trade_id DESC LIMIT ?", (limit,))]

    def close_trade(self, trade_id, exit_price, pnl):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE trades SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ? WHERE trade_id = ?",
                        (datetime.now().isoformat(), exit_price, pnl, trade_id))

paper_db = PaperDB()