import sqlite3
import os
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime

# Local SQLite DB to avoid paid DB infrastructure.
DB_PATH = os.path.join(os.path.dirname(__file__), 'paper_db.sqlite3')

def init_db() -> None:
    """Initializes the SQLite database with the required 'trades' table."""
    conn = sqlite3.connect(DB_PATH)
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
            status TEXT NOT NULL, -- 'Open' or 'Closed'
            exit_time TEXT,
            exit_price REAL,
            pnl REAL,
            highest_price REAL, -- For Trailing Stop calculation
            lowest_price REAL   -- For Trailing Stop calculation
        )
    ''')
    conn.commit()
    conn.close()

def execute_query(query: str, parameters: tuple = ()) -> None:
    """Executes an INSERT/UPDATE/DELETE query securely using sqlite3."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, parameters)
    conn.commit()
    conn.close()

def fetch_query(query: str, parameters: tuple = ()) -> List[tuple]:
    """Fetches data from SQLite and returns a list of tuples."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(query, parameters)
    results = cursor.fetchall()
    conn.close()
    return results

def fetch_dataframe(query: str, parameters: tuple = ()) -> pd.DataFrame:
    """Fetches data directly into a Pandas DataFrame for vectorized reporting."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(query, conn, params=parameters)
    conn.close()
    return df

def get_open_trades() -> List[Dict]:
    """Retrieves all currently 'Open' trades as a list of dictionaries."""
    query = "SELECT * FROM trades WHERE status = 'Open'"
    rows = fetch_query(query)
    columns = [
        'trade_id', 'ticker', 'direction', 'entry_time', 'entry_price',
        'sl_price', 'tp_price', 'position_size', 'status', 'exit_time',
        'exit_price', 'pnl', 'highest_price', 'lowest_price'
    ]
    return [dict(zip(columns, row)) for row in rows]

# Initialize on import
init_db()
