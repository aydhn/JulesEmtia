import sqlite3
import os
from core.logger import get_logger

logger = get_logger()

class PaperDB:
    def __init__(self):
        self.db_path = "paper_db.sqlite3"
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    direction TEXT,
                    entry_price REAL,
                    sl_price REAL,
                    tp_price REAL,
                    position_size REAL,
                    status TEXT,
                    exit_price REAL,
                    pnl REAL,
                    cost REAL
                )
            ''')
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            logger.critical(f"Veritabanı başlatma hatası: {e}")

    def execute(self, query: str, params: tuple = ()):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
        except sqlite3.Error as e:
            logger.error(f"Sorgu Hatası ({query}): {e}")

    def fetch_all(self, query: str, params: tuple = ()):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            return rows
        except sqlite3.Error as e:
            logger.error(f"Sorgu Hatası ({query}): {e}")
            return []
