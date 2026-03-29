import sqlite3
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from ed_quant_engine.config import DB_PATH
from ed_quant_engine.logger import log

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
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
    conn.commit()
    conn.close()
    log.info("SQLite Database initialized at %s", DB_PATH)

def open_trade(trade_data: Dict[str, Any]) -> int:
    """Inserts a new open trade and returns the trade_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        trade_data['ticker'], trade_data['direction'], datetime.now().isoformat(),
        trade_data['entry_price'], trade_data['sl_price'], trade_data['tp_price'],
        trade_data['position_size'], 'Open'
    ))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log.info(f"Trade Opened [ID: {trade_id}]: {trade_data['ticker']} {trade_data['direction']} @ {trade_data['entry_price']}")
    return trade_id

def close_trade(trade_id: int, exit_price: float, pnl: float) -> None:
    """Marks a trade as Closed and logs exit details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
        WHERE trade_id = ?
    ''', (datetime.now().isoformat(), exit_price, pnl, trade_id))
    conn.commit()
    conn.close()
    log.info(f"Trade Closed [ID: {trade_id}]: Exit @ {exit_price}, PnL: {pnl}")

def update_sl_price(trade_id: int, new_sl: float) -> None:
    """Updates the Stop-Loss price for Trailing Stop or Breakeven."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE trades SET sl_price = ? WHERE trade_id = ?', (new_sl, trade_id))
    conn.commit()
    conn.close()
    log.info(f"Trade [ID: {trade_id}] SL updated to {new_sl}")

def get_open_trades() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM trades WHERE status = "Open"')
    columns = [desc[0] for desc in cursor.description]
    trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return trades

def get_all_closed_trades() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query('SELECT * FROM trades WHERE status = "Closed"', conn)
    conn.close()
    return df

# Initialize on import
initialize_db()
