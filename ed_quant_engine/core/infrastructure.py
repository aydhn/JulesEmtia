import logging
import sqlite3
import pandas as pd
import os
import requests

# ----------------- LOGGING ALTYAPISI (Phase 8) -----------------
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Dosyaya yazma
    os.makedirs("logs", exist_ok=True)

    # Check if handlers already exist to prevent duplicate logs
    if not logger.handlers:
        from logging.handlers import RotatingFileHandler
        fh = RotatingFileHandler('logs/quant_engine.log', maxBytes=5*1024*1024, backupCount=3)
        fh.setLevel(logging.INFO)

        # Konsola yazma
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Format (Kurumsal Standart)
        formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger

logger = setup_logger("ED_Capital_Quant")

# ----------------- TELEGRAM ALTYAPISI (Phase 2) -----------------
class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials missing, message not sent.")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"Telegram error: {response.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

# ----------------- DATABASE ALTYAPISI (Phase 5) -----------------
class PaperDB:
    def __init__(self, db_path="data/paper_db.sqlite3"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        with self._get_conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    direction TEXT,
                    entry_time TIMESTAMP,
                    entry_price REAL,
                    sl_price REAL,
                    tp_price REAL,
                    position_size REAL,
                    status TEXT,
                    exit_time TIMESTAMP,
                    exit_price REAL,
                    pnl REAL,
                    commission REAL,
                    slippage REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY,
                    current_balance REAL
                )
            ''')
            # Initialize balance if empty
            cursor = conn.cursor()
            cursor.execute("SELECT current_balance FROM balance WHERE id=1")
            if not cursor.fetchone():
                from .config import INITIAL_CAPITAL
                cursor.execute("INSERT INTO balance (id, current_balance) VALUES (1, ?)", (INITIAL_CAPITAL,))
            conn.commit()

    def get_balance(self) -> float:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_balance FROM balance WHERE id=1")
            row = cursor.fetchone()
            return row[0] if row else 10000.0

    def update_balance(self, new_balance: float):
        with self._get_conn() as conn:
            conn.execute("UPDATE balance SET current_balance = ? WHERE id=1", (new_balance,))
            conn.commit()

    def get_open_trades(self) -> pd.DataFrame:
        with self._get_conn() as conn:
            return pd.read_sql_query("SELECT * FROM trades WHERE status = 'Open'", conn)

    def get_closed_trades(self) -> pd.DataFrame:
        with self._get_conn() as conn:
            return pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed'", conn)

    def update_sl(self, trade_id: int, new_sl: float):
        """Phase 12: SL update for state recovery."""
        with self._get_conn() as conn:
            conn.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
            conn.commit()

# Create a global db instance for legacy imports if needed
db = PaperDB()
