import sqlite3
import os
from typing import Dict, Any, List, Optional
from logger import get_logger

logger = get_logger("paper_db")

DB_PATH = "paper_db.sqlite3"

def init_db():
    """Initializes the SQLite database with the necessary tables."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create trades table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            entry_price REAL NOT NULL,
            sl_price REAL NOT NULL,
            tp_price REAL NOT NULL,
            position_size REAL NOT NULL,
            status TEXT NOT NULL,
            exit_time TIMESTAMP,
            exit_price REAL,
            pnl REAL
        )
        ''')

        # Create portfolio state table to persist total balance across restarts
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance REAL NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Initialize default portfolio balance if not exists
        cursor.execute('''
        INSERT OR IGNORE INTO portfolio (id, balance) VALUES (1, 10000.0)
        ''')

        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

def get_balance() -> float:
    """Gets the current portfolio balance."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM portfolio WHERE id = 1")
        row = cursor.fetchone()
        if row:
            return row[0]
        return 10000.0  # Default if missing
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        return 10000.0
    finally:
        if conn:
            conn.close()

def update_balance(new_balance: float):
    """Updates the portfolio balance."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE portfolio SET balance = ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1", (new_balance,))
        conn.commit()
        logger.info(f"Portfolio balance updated to: ${new_balance:.2f}")
    except Exception as e:
        logger.error(f"Failed to update balance: {e}")
    finally:
        if conn:
            conn.close()

def open_trade(trade_data: Dict[str, Any]) -> Optional[int]:
    """Adds a new open trade to the database."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['ticker'],
            trade_data['direction'],
            trade_data['entry_time'],
            trade_data['entry_price'],
            trade_data['sl_price'],
            trade_data['tp_price'],
            trade_data['position_size'],
            'Open'
        ))
        conn.commit()
        trade_id = cursor.lastrowid
        logger.info(f"Opened new trade ID {trade_id}: {trade_data['direction']} {trade_data['ticker']} @ {trade_data['entry_price']}")
        return trade_id
    except Exception as e:
        logger.error(f"Failed to open trade: {e}")
        return None
    finally:
        if conn:
            conn.close()

def close_trade(trade_id: int, exit_time: str, exit_price: float, pnl: float):
    """Closes an existing trade and updates its PnL."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
        WHERE trade_id = ? AND status = 'Open'
        ''', (exit_time, exit_price, pnl, trade_id))
        conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"Closed trade ID {trade_id} @ {exit_price}. PnL: ${pnl:.2f}")
            # Update overall portfolio balance
            current_balance = get_balance()
            update_balance(current_balance + pnl)
        else:
            logger.warning(f"Trade ID {trade_id} not found or already closed.")
    except Exception as e:
        logger.error(f"Failed to close trade: {e}")
    finally:
        if conn:
            conn.close()

def get_open_trades() -> List[Dict[str, Any]]:
    """Retrieves all open trades."""
    conn = None
    trades = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # To return dict-like objects
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
        rows = cursor.fetchall()
        for row in rows:
            trades.append(dict(row))
        return trades
    except Exception as e:
        logger.error(f"Failed to get open trades: {e}")
        return []
    finally:
        if conn:
            conn.close()

def update_sl_price(trade_id: int, new_sl: float):
    """Updates the Stop Loss price for an open trade (Trailing Stop)."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE trades
        SET sl_price = ?
        WHERE trade_id = ? AND status = 'Open'
        ''', (new_sl, trade_id))
        conn.commit()
        logger.info(f"Updated SL for trade ID {trade_id} to {new_sl:.4f}")
    except Exception as e:
        logger.error(f"Failed to update SL for trade ID {trade_id}: {e}")
    finally:
        if conn:
            conn.close()

def get_closed_trades(limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieves closed trades, useful for reporting and Kelly calculation."""
    conn = None
    trades = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        for row in rows:
            trades.append(dict(row))
        return trades
    except Exception as e:
        logger.error(f"Failed to get closed trades: {e}")
        return []
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()
