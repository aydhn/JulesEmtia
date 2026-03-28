import sqlite3
import os
from datetime import datetime
from src.core.logger import logger
from src.core.config import DB_PATH

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            direction TEXT,
            entry_time TEXT,
            entry_price REAL,
            sl_price REAL,
            tp_price REAL,
            position_size REAL,
            status TEXT,
            exit_time TEXT,
            exit_price REAL,
            pnl REAL
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Paper DB initialized.")

def open_trade(ticker: str, direction: str, entry_price: float, sl_price: float, tp_price: float, position_size: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (ticker, direction, datetime.now().isoformat(), entry_price, sl_price, tp_price, position_size, 'Open'))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Opened trade #{trade_id} {direction} {ticker} at {entry_price}")
    return trade_id

def update_sl_price(trade_id: int, new_sl: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE trades SET sl_price = ? WHERE trade_id = ?', (new_sl, trade_id))
    conn.commit()
    conn.close()
    logger.info(f"Updated SL for trade #{trade_id} to {new_sl}")

def close_trade(trade_id: int, exit_price: float, pnl: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trades
        SET status = ?, exit_time = ?, exit_price = ?, pnl = ?
        WHERE trade_id = ?
    ''', ('Closed', datetime.now().isoformat(), exit_price, pnl, trade_id))
    conn.commit()
    conn.close()
    logger.info(f"Closed trade #{trade_id} at {exit_price} with PNL {pnl}")

def get_open_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_closed_trades():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Closed'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
