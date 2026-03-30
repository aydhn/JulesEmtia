import sqlite3
import os
import datetime
from typing import Dict, List, Any, Optional
from src.logger import get_logger

logger = get_logger("paper_db")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "paper_db.sqlite3")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    """Initializes the SQLite database with the required schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
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
            pnl REAL,
            comment TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

def open_trade(ticker: str, direction: str, entry_price: float, sl_price: float, tp_price: float, position_size: float, comment: str = "") -> int:
    """Inserts a new open trade into the database and returns the trade_id."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?)
    """, (ticker, direction, now, entry_price, sl_price, tp_price, position_size, comment))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Opened new trade #{trade_id} on {ticker} {direction} at {entry_price:.4f}")
    return trade_id

def close_trade(trade_id: int, exit_price: float, pnl: float, comment: str = "") -> bool:
    """Closes an open trade and calculates the PNL."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()

    # Get current comment to append
    cursor.execute("SELECT comment FROM trades WHERE trade_id = ?", (trade_id,))
    res = cursor.fetchone()
    current_comment = res[0] if res else ""
    new_comment = f"{current_comment} | Closed: {comment}".strip(" |")

    cursor.execute("""
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?, comment = ?
        WHERE trade_id = ? AND status = 'Open'
    """, (now, exit_price, pnl, new_comment, trade_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if success:
        logger.info(f"Closed trade #{trade_id} at {exit_price:.4f} with PNL: {pnl:.2f}")
    return success

def update_sl_price(trade_id: int, new_sl: float) -> bool:
    """Updates the stop-loss price for trailing stops or breakeven."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE trades
        SET sl_price = ?
        WHERE trade_id = ? AND status = 'Open'
    """, (new_sl, trade_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    if success:
        logger.debug(f"Updated SL for trade #{trade_id} to {new_sl:.4f}")
    return success

def get_open_trades() -> List[Dict[str, Any]]:
    """Returns a list of all currently open trades."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_closed_trades() -> List[Dict[str, Any]]:
    """Returns a list of all closed trades for performance reporting."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE status = 'Closed'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Run init on import
init_db()
