import sqlite3
from src.config import DB_PATH
from src.logger import logger
from datetime import datetime
from typing import List, Dict, Optional

class PaperDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
        self.cursor.execute('''
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
                pnl REAL
            )
        ''')
        self.conn.commit()

    def open_trade(self, trade_data: Dict) -> int:
        query = '''
            INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        values = (
            trade_data['ticker'],
            trade_data['direction'],
            datetime.now().isoformat(),
            trade_data['entry_price'],
            trade_data['sl_price'],
            trade_data['tp_price'],
            trade_data['position_size'],
            'Open'
        )
        self.cursor.execute(query, values)
        self.conn.commit()
        return self.cursor.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, pnl: float) -> None:
        query = '''
            UPDATE trades
            SET status = ?, exit_time = ?, exit_price = ?, pnl = ?
            WHERE trade_id = ?
        '''
        self.cursor.execute(query, ('Closed', datetime.now().isoformat(), exit_price, pnl, trade_id))
        self.conn.commit()

    def get_open_trades(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
        columns = [column[0] for column in self.cursor.description]
        return [dict(zip(columns, row)) for row in self.cursor.fetchall()]

    def close(self):
        self.conn.close()

db = PaperDB()
