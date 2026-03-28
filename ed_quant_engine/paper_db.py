import sqlite3
import os
from config import DB_PATH
from logger import get_logger

log = get_logger()

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
            pnl REAL,
            slippage_cost REAL
        )
    ''')
    conn.commit()
    conn.close()
    log.info("SQLite Database initialized/verified.")

def open_trade(ticker: str, direction: str, entry_time: str, entry_price: float, sl_price: float, tp_price: float, position_size: float, slippage_cost: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, exit_time, exit_price, pnl, slippage_cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', NULL, NULL, NULL, ?)
    ''', (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, slippage_cost))
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    log.info(f"Opened Trade {trade_id}: {direction} {ticker} @ {entry_price}")
    return trade_id

def close_trade(trade_id: int, exit_time: str, exit_price: float, pnl: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
        WHERE trade_id = ?
    ''', (exit_time, exit_price, pnl, trade_id))
    conn.commit()
    conn.close()
    log.info(f"Closed Trade {trade_id} @ {exit_price} | PnL: {pnl}")

def update_sl_price(trade_id: int, new_sl: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trades
        SET sl_price = ?
        WHERE trade_id = ?
    ''', (new_sl, trade_id))
    conn.commit()
    conn.close()
    log.info(f"Updated SL for Trade {trade_id} to {new_sl}")

def get_open_positions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_closed_trades(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows
