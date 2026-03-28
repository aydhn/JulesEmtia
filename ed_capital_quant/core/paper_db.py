import sqlite3
import pandas as pd
from core.logger import logger

class PaperDB:
    def __init__(self, db_name="paper_db.sqlite3"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT, direction TEXT, entry_time TEXT, entry_price REAL,
                sl_price REAL, tp_price REAL, position_size REAL,
                status TEXT, exit_time TEXT, exit_price REAL, pnl REAL
            )
        ''')
        self.conn.commit()

    def open_trade(self, data: dict):
        df = pd.DataFrame([data])
        df.to_sql('trades', self.conn, if_exists='append', index=False)
        logger.info(f"DB: Yeni işlem açıldı -> {data['ticker']} {data['direction']}")

    def get_open_trades(self):
        return pd.read_sql("SELECT * FROM trades WHERE status='Open'", self.conn)

    def update_sl(self, trade_id: int, new_sl: float):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE trades SET sl_price=? WHERE trade_id=?", (new_sl, trade_id))
        self.conn.commit()

    def close_trade(self, trade_id: int, exit_price: float, exit_time: str, pnl: float):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE trades SET status='Closed', exit_price=?, exit_time=?, pnl=?
            WHERE trade_id=?
        ''', (exit_price, exit_time, pnl, trade_id))
        self.conn.commit()
        logger.info(f"DB: İşlem Kapatıldı ID:{trade_id} PNL:{pnl:.2f}")
