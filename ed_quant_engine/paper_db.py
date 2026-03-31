import sqlite3
import os
import threading
from typing import Dict, Any, List, Optional
from logger import logger

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'paper_db.sqlite3')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

class PaperDB:
    """
    Lightweight SQLite Database Manager for tracking paper trades,
    Pnl, and execution details locally without paid databases.
    Follows Quant standards for atomicity and local persistence.
    """
    _local = threading.local()

    @classmethod
    def get_connection(cls):
        """Thread-local SQLite connection."""
        if not hasattr(cls._local, "connection"):
            cls._local.connection = sqlite3.connect(DB_FILE, check_same_thread=False)
            cls._local.connection.row_factory = sqlite3.Row
        return cls._local.connection

    @classmethod
    def initialize_db(cls):
        """Creates the necessary tables if they do not exist."""
        try:
            conn = cls.get_connection()
            cursor = conn.cursor()

            # Trades table
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
                    pnl REAL,
                    net_pnl REAL,
                    spread REAL,
                    slippage REAL,
                    reason TEXT
                )
            ''')

            # State table (Balance tracking)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL
                )
            ''')

            # Initialize starting balance if empty
            cursor.execute('SELECT value FROM state WHERE key="balance"')
            if cursor.fetchone() is None:
                start_balance = float(os.getenv("PAPER_STARTING_BALANCE", 10000.0))
                cursor.execute('INSERT INTO state (key, value) VALUES (?, ?)', ('balance', start_balance))

            conn.commit()
            logger.info("Local SQLite Database initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize SQLite Database: {e}")

    @classmethod
    def execute_query(cls, query: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor

    @classmethod
    def fetch_all(cls, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        cursor = cls.execute_query(query, params)
        return cursor.fetchall()

    @classmethod
    def fetch_one(cls, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        cursor = cls.execute_query(query, params)
        return cursor.fetchone()

    @classmethod
    def update_balance(cls, amount: float):
        """Updates the current balance."""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE state SET value = value + ? WHERE key = 'balance'", (amount,))
        conn.commit()

    @classmethod
    def get_balance(cls) -> float:
        """Gets current balance."""
        row = cls.fetch_one("SELECT value FROM state WHERE key='balance'")
        return row['value'] if row else 0.0

# Initialize immediately
PaperDB.initialize_db()
