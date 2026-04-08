import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
from src.logger import get_logger

logger = get_logger()

DB_PATH = "data/paper_db.sqlite3"

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
            pnl_pct REAL,
            is_breakeven INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY,
            balance REAL
        )
    ''')
    # Initialize balance if not exists
    cursor.execute('SELECT COUNT(*) FROM portfolio')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO portfolio (id, balance) VALUES (1, 10000.0)')
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def get_balance() -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM portfolio WHERE id = 1')
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else 10000.0

def update_balance(new_balance: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE portfolio SET balance = ? WHERE id = 1', (new_balance,))
    conn.commit()
    conn.close()

def open_trade(ticker: str, direction: str, entry_price: float, sl_price: float, tp_price: float, position_size: float) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
    ''', (ticker, direction, now, entry_price, sl_price, tp_price, position_size))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Opened Trade #{trade_id} {direction} {ticker} @ {entry_price}")
    return trade_id

def close_trade(trade_id: int, exit_price: float) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT ticker, direction, entry_price, position_size FROM trades WHERE trade_id = ? AND status = "Open"', (trade_id,))
    trade = cursor.fetchone()
    if not trade:
        conn.close()
        return {}

    ticker, direction, entry_price, pos_size = trade

    if direction == 'Long':
        pnl = (exit_price - entry_price) * pos_size
        pnl_pct = (exit_price - entry_price) / entry_price
    else:
        pnl = (entry_price - exit_price) * pos_size
        pnl_pct = (entry_price - exit_price) / entry_price

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?, pnl_pct = ?
        WHERE trade_id = ?
    ''', (now, exit_price, pnl, pnl_pct, trade_id))

    conn.commit()
    conn.close()

    # Update balance
    current_balance = get_balance()
    update_balance(current_balance + pnl)

    logger.info(f"Closed Trade #{trade_id} {ticker} @ {exit_price} | PnL: {pnl:.2f}")
    return {"trade_id": trade_id, "pnl": pnl, "pnl_pct": pnl_pct}

def update_sl_price(trade_id: int, new_sl: float, is_breakeven: int = 0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE trades SET sl_price = ?, is_breakeven = max(is_breakeven, ?) WHERE trade_id = ?', (new_sl, is_breakeven, trade_id))
    conn.commit()
    conn.close()
    logger.info(f"Updated SL for Trade #{trade_id} to {new_sl}")

def get_open_trades() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM trades WHERE status = "Open"')
    columns = [col[0] for col in cursor.description]
    trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return trades

def get_closed_trades() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM trades WHERE status = "Closed"', conn)
    conn.close()
    return df
