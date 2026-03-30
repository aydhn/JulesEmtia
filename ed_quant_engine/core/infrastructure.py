import logging
import sqlite3
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import os
import requests

# ----------------- LOGGING ALTYAPISI (Phase 8) -----------------
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Dosyaya yazma
    os.makedirs("logs", exist_ok=True)
    fh = logging.FileHandler('logs/quant_engine.log')
    fh.setLevel(logging.INFO)

    # Konsola yazma
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Format (Kurumsal Standart)
    formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    if not logger.handlers:
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

# ----------------- BROKER ABSTRACTION (Phase 24) -----------------
class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, lot_size: float, sl_price: float, tp_price: float, current_price: float, spread_cost: float, slippage_cost: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> pd.DataFrame:
        pass

class PaperBroker(BaseBroker):
    def __init__(self, db: PaperDB):
        self.db = db

    def get_account_balance(self) -> float:
        return self.db.get_balance()

    def get_open_positions(self) -> pd.DataFrame:
        return self.db.get_open_trades()

    def place_market_order(self, ticker: str, direction: str, lot_size: float, sl_price: float, tp_price: float, current_price: float, spread_cost: float, slippage_cost: float) -> Dict[str, Any]:

        # Maliyetli giriş simülasyonu (Phase 21)
        if direction == "Long":
            entry_price = current_price + (spread_cost / 2) + slippage_cost
        else:
            entry_price = current_price - (spread_cost / 2) - slippage_cost

        with self.db._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, commission, slippage)
                VALUES (?, ?, datetime('now'), ?, ?, ?, ?, 'Open', ?, ?)
            ''', (ticker, direction, entry_price, sl_price, tp_price, lot_size, spread_cost, slippage_cost))
            trade_id = cursor.lastrowid
            conn.commit()

            logger.info(f"AUDIT TRAIL: Paper Trade Execution Receipt - ID: {trade_id} | {direction} {lot_size} lots {ticker} @ {entry_price:.4f} (Spread: {spread_cost}, Slippage: {slippage_cost})")

            return {
                "trade_id": trade_id,
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry_price,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "size": lot_size
            }

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        with self.db._get_conn() as conn:
            conn.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
            conn.commit()
            logger.info(f"Trailing Stop updated for Trade {trade_id} to {new_sl:.4f}")
            return True

    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> bool:
        with self.db._get_conn() as conn:
            conn.execute('''
                UPDATE trades
                SET status = 'Closed', exit_time = datetime('now'), exit_price = ?, pnl = ?
                WHERE trade_id = ?
            ''', (exit_price, pnl, trade_id))
            conn.commit()

        new_balance = self.get_account_balance() + pnl
        self.db.update_balance(new_balance)
        logger.info(f"Position {trade_id} closed at {exit_price:.4f} | PnL: {pnl:.2f} | New Balance: {new_balance:.2f}")
        return True
