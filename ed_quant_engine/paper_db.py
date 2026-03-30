import sqlite3
import pandas as pd
from typing import List, Dict, Optional
import time
from config import DB_PATH
from logger import log

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
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
    except Exception as e:
        log.error(f"Failed to initialize DB: {e}")
    finally:
        conn.close()

def execute_query(query: str, params: tuple = ()) -> Optional[List[tuple]]:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            result = c.fetchall()
            return result
        else:
            conn.commit()
            return None
    except Exception as e:
        log.error(f"DB Query Error: {e} - Query: {query}")
        return None
    finally:
        conn.close()

def get_open_trades() -> List[Dict]:
    rows = execute_query("SELECT trade_id, ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status FROM trades WHERE status='Open'")
    if not rows: return []
    keys = ["trade_id", "ticker", "direction", "entry_time", "entry_price", "sl_price", "tp_price", "position_size", "status"]
    return [dict(zip(keys, row)) for row in rows]

def get_all_trades_df() -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM trades", conn)
        return df
    except Exception as e:
        log.error(f"Error fetching trades DF: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

init_db()
