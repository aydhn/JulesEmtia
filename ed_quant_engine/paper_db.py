import sqlite3
import os
import pandas as pd
from typing import Optional, Dict, Any, List
from utils.logger import setup_logger

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

def open_trade(trade_data: dict) -> int:
    """Records a new 'Open' trade."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')
    """, (trade_data['ticker'], trade_data['direction'], trade_data['entry_time'], trade_data['entry_price'], trade_data['sl_price'], trade_data['tp_price'], trade_data['position_size']))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Yeni İşlem Açıldı [ID: {trade_id}]: {trade_data['direction']} {trade_data['ticker']} @ {trade_data['entry_price']:.4f} (Lot: {trade_data['position_size']:.4f}) | SL: {trade_data['sl_price']:.4f} TP: {trade_data['tp_price']:.4f}")
    return trade_id

def close_trade(trade_id: int, exit_time: str, exit_price: float, pnl: float) -> None:
    """Marks a trade as 'Closed' and records exit details."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Fetch entry price for percentage calculation
    cursor.execute("SELECT entry_price, direction, position_size FROM trades WHERE trade_id = ?", (trade_id,))
    res = cursor.fetchone()
    if res:
        entry_price = res[0]
        pnl_percent = (pnl / (entry_price * res[2])) * 100 if entry_price and res[2] else 0.0
    else:
        pnl_percent = 0.0

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

def get_open_trades() -> List[Dict[str, Any]]:
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

def get_balance() -> float:
    initial_balance = float(os.getenv("INITIAL_BALANCE", "10000.0"))
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT sum(pnl) FROM trades WHERE status = 'Closed'")
    total_pnl = cursor.fetchone()[0] or 0.0
    conn.close()
    return initial_balance + total_pnl

# Start Db immediately upon import
init_db()
