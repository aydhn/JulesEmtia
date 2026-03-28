import sqlite3
import pandas as pd
from typing import Dict, Any, List
import os

from core.logger import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "paper_db.sqlite3")

def init_db():
    """Kurumsal SQLite veritabanını başlatır."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Açık/Kapalı işlemlerin kaydedileceği ana tablo
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
            status TEXT NOT NULL, -- 'Open' veya 'Closed'
            exit_time TEXT,
            exit_price REAL,
            pnl REAL, -- Net Kâr/Zarar
            fees REAL -- Kesilen Toplam Spread ve Kayma Maliyeti
        )
    ''')

    # Makroekonomik, ML ve Korelasyon sınırlarının loglanacağı tablo (Opsiyonel Audit Trail)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("SQLite Paper Trade veritabanı başarıyla başlatıldı.")

def execute_query(query: str, params: tuple = ()) -> None:
    """Veritabanına yazma (INSERT, UPDATE) işlemlerini yapar."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
    except Exception as e:
        logger.error(f"Veritabanı yazma hatası: {e} - Sorgu: {query}")

def fetch_query(query: str, params: tuple = ()) -> List[tuple]:
    """Veritabanından veri (SELECT) okur."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Veritabanı okuma hatası: {e} - Sorgu: {query}")
        return []

def fetch_dataframe(query: str, params: tuple = ()) -> pd.DataFrame:
    """Veritabanından veriyi doğrudan Pandas DataFrame olarak çeker."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn, params=params)
            return df
    except Exception as e:
        logger.error(f"Veritabanı DF çekme hatası: {e}")
        return pd.DataFrame()

# Initialize upon import
init_db()