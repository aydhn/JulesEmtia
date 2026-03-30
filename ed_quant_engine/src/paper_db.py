import sqlite3
import os
import json
import uuid
from datetime import datetime
from .config import DB_PATH
from .logger import log_info, log_error

def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
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
        # Hesap durumu tablosu (Account Equity)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                balance REAL,
                last_updated TEXT
            )
        ''')
        # İlk bakiye (Eğer boşsa 10.000$ ile başlat)
        cursor.execute('SELECT COUNT(*) FROM account')
        if cursor.fetchone()[0] == 0:
            cursor.execute('INSERT INTO account (balance, last_updated) VALUES (?, ?)',
                           (10000.0, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        log_error(f"DB Kurulum Hatası: {e}")
    finally:
        conn.close()

def open_trade(ticker: str, direction: str, entry_price: float, sl_price: float, tp_price: float, position_size: float) -> str:
    trade_id = str(uuid.uuid4())
    entry_time = datetime.now().isoformat()
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (trade_id, ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Open')
        ''', (trade_id, ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size))
        conn.commit()
        return trade_id
    except Exception as e:
        log_error(f"İşlem Açılamadı ({ticker}): {e}")
    finally:
        conn.close()

def close_trade(trade_id: str, exit_price: float, pnl: float):
    exit_time = datetime.now().isoformat()
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades
            SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
            WHERE trade_id = ?
        ''', (exit_time, exit_price, pnl, trade_id))

        # Bakiyeyi güncelle
        cursor.execute('SELECT balance FROM account WHERE id = 1')
        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + pnl
        cursor.execute('UPDATE account SET balance = ?, last_updated = ? WHERE id = 1',
                       (new_balance, exit_time))
        conn.commit()
    except Exception as e:
        log_error(f"İşlem Kapatılamadı ({trade_id}): {e}")
    finally:
        conn.close()

def get_open_trades() -> list:
    try:
        conn = _get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        log_error(f"Açık İşlemler Çekilemedi: {e}")
        return []
    finally:
        conn.close()

def get_closed_trades() -> list:
    try:
        conn = _get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time DESC")
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        log_error(f"Kapalı İşlemler Çekilemedi: {e}")
        return []
    finally:
        conn.close()

def update_sl_price(trade_id: str, new_sl: float):
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
        conn.commit()
    except Exception as e:
        log_error(f"Stop-Loss Güncellenemedi ({trade_id}): {e}")
    finally:
        conn.close()

def get_account_balance() -> float:
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM account WHERE id = 1")
        return cursor.fetchone()[0]
    except Exception as e:
        log_error(f"Bakiye Okunamadı: {e}")
        return 10000.0  # Fallback
    finally:
        conn.close()
