import sqlite3
import os
import pandas as pd
from typing import Optional, Dict, Any, List
from logger import setup_logger

logger = setup_logger("PaperDB")

DB_FILE = os.getenv("DB_NAME", "paper_db.sqlite3")

def init_db() -> None:
    """Initializes the SQLite database schema for robust local paper trading."""
    logger.info(f"Veritabanı başlatılıyor: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_time TIMESTAMP NOT NULL,
            entry_price REAL NOT NULL,
            sl_price REAL NOT NULL,
            tp_price REAL NOT NULL,
            position_size REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            exit_time TIMESTAMP,
            exit_price REAL,
            pnl REAL,
            pnl_percent REAL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Veritabanı şeması doğrulandı.")

def open_trade(ticker: str, direction: str, entry_time: str, entry_price: float, sl: float, tp: float, size: float) -> int:
    """Records a new 'Open' trade."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
    """, (ticker, direction, entry_time, entry_price, sl, tp, size))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Yeni İşlem Açıldı [ID: {trade_id}]: {direction} {ticker} @ {entry_price:.4f} (Lot: {size:.4f}) | SL: {sl:.4f} TP: {tp:.4f}")
    return trade_id

def close_trade(trade_id: int, exit_time: str, exit_price: float, pnl: float, pnl_percent: float) -> None:
    """Marks a trade as 'Closed' and records exit details."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE trades
        SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?, pnl_percent = ?
        WHERE trade_id = ?
    """, (exit_time, exit_price, pnl, pnl_percent, trade_id))
    conn.commit()
    conn.close()
    logger.info(f"İşlem Kapandı [ID: {trade_id}]: Çıkış @ {exit_price:.4f} | PNL: {pnl:.2f} (%{pnl_percent:.2f})")

def update_sl_price(trade_id: int, new_sl: float) -> None:
    """Updates the stop-loss price dynamically for trailing stop or breakeven logic."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
    conn.commit()
    conn.close()
    logger.info(f"SL Güncellendi [ID: {trade_id}]: Yeni SL: {new_sl:.4f}")

def get_open_positions() -> List[Dict[str, Any]]:
    """Retrieves all currently 'Open' trades."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'Open'", conn)
    conn.close()
    return df.to_dict('records')

def get_closed_trades() -> pd.DataFrame:
    """Retrieves all 'Closed' trades for performance reporting and ML calculations."""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed'", conn)
    conn.close()
    return df

# Start Db immediately upon import
init_db()
