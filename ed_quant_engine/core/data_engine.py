import sqlite3
import yfinance as yf
import pandas as pd
import time
from functools import wraps
from system.logger import log

def exponential_backoff(retries=3, base_delay=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    log.warning(f"API Error (Attempt {attempt+1}): {e}")
                    time.sleep(base_delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

class DataEngine:
    @staticmethod
    @exponential_backoff(retries=3)
    def fetch_mtf_data(ticker: str) -> dict:
        """Phase 16: MTF Data Fetching. HTF (1D) and LTF (1H) sync."""
        htf = yf.download(ticker, period="2y", interval="1d", progress=False)
        ltf = yf.download(ticker, period="1mo", interval="1h", progress=False)
        if htf.empty or ltf.empty:
            return None

        # Strip timezone info to avoid MergeError during asof merge
        if htf.index.tz is not None:
            htf.index = htf.index.tz_localize(None)
        if ltf.index.tz is not None:
            ltf.index = ltf.index.tz_localize(None)

        return {"HTF": htf.ffill(), "LTF": ltf.ffill()}

class PaperDB:
    """Phase 5: Light, persistent, local SQLite Paper Trade DB"""
    def __init__(self, db_name="paper_db.sqlite3"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, direction TEXT,
            entry_time TEXT, entry_price REAL, sl_price REAL, tp_price REAL,
            position_size REAL, status TEXT, exit_time TEXT, exit_price REAL, pnl REAL)''')
        self.conn.commit()

    def open_trade(self, t: str, dir: str, p: float, sl: float, tp: float, size: float):
        self.cursor.execute("""INSERT INTO trades
            (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
            VALUES (?, ?, datetime('now'), ?, ?, ?, ?, 'OPEN')""", (t, dir, p, sl, tp, size))
        self.conn.commit()

    def update_sl(self, trade_id: int, new_sl: float):
        self.cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
        self.conn.commit()

    def close_trade(self, trade_id: int, exit_price: float, pnl: float):
        self.cursor.execute("""UPDATE trades SET status='CLOSED', exit_time=datetime('now'),
            exit_price=?, pnl=? WHERE trade_id=?""", (exit_price, pnl, trade_id))
        self.conn.commit()

    def get_open_positions(self):
        try:
            return pd.read_sql_query("SELECT * FROM trades WHERE status='OPEN'", self.conn)
        except Exception as e:
            log.error(f"Error fetching open positions: {e}")
            return pd.DataFrame()

db = PaperDB()
