import sqlite3
import pandas as pd
from typing import Dict, List, Any
import time
from ed_quant_engine.core.broker_base import BaseBroker
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config

logger = setup_logger("PaperBroker")

class PaperBroker(BaseBroker):
    """SQLite-backed Virtual Broker implementing Slippage, Spread and Trailing Stops."""
    def __init__(self, db_path=Config.DB_PATH, initial_balance=Config.BASE_CAPITAL):
        self.db_path = db_path
        self.balance = initial_balance
        self._init_db()
        self._load_balance()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT, direction TEXT,
                    entry_time TEXT, entry_price REAL,
                    sl_price REAL, tp_price REAL, position_size REAL,
                    status TEXT, exit_time TEXT, exit_price REAL, pnl REAL,
                    slippage_cost REAL, reason TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY,
                    balance REAL
                )
            ''')
            # Initialize balance if empty
            cursor.execute('SELECT balance FROM account WHERE id=1')
            if not cursor.fetchone():
                cursor.execute('INSERT INTO account (id, balance) VALUES (1, ?)', (self.balance,))
            conn.commit()

    def _load_balance(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM account WHERE id=1')
            row = cursor.fetchone()
            if row:
                self.balance = row[0]

    def get_account_balance(self) -> float:
        self._load_balance()
        return self.balance

    def update_balance(self, pnl: float):
        self.balance += pnl
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE account SET balance = ? WHERE id=1', (self.balance,))
            conn.commit()

    def get_open_positions(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT trade_id, ticker, direction, entry_price, sl_price, tp_price, position_size
                FROM trades WHERE status = "Open"
            ''')
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def calculate_slippage_and_spread(self, ticker: str, atr: float, price: float) -> float:
        """Dynamic Spread & ATR-Adjusted Slippage (Phase 21)"""
        base_spread = 0.0002 # Default 2 bps
        if "TRY" in ticker:
            base_spread = 0.0010 # 10 bps for Exotic
        elif ticker in ["GC=F", "CL=F"]:
            base_spread = 0.0005 # 5 bps for Majors

        # If ATR is high, slippage increases linearly
        volatility_penalty = atr * 0.1 # Placeholder: 10% of ATR added as slippage

        total_cost_per_unit = (price * base_spread) + volatility_penalty
        return total_cost_per_unit

    def place_market_order(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Executes trade with costs and saves to SQLite."""
        ticker = signal['ticker']
        direction = signal['direction']
        raw_price = signal['entry_price']
        atr = signal['atr']

        # Calculate Costs
        cost = self.calculate_slippage_and_spread(ticker, atr, raw_price)

        # Apply Slippage to Entry Price
        entry_price = raw_price + cost if direction == "Long" else raw_price - cost

        # Recalculate SL/TP based on new entry (Costs eat into RR)
        sl_dist = abs(raw_price - signal['sl_price'])
        sl_price = entry_price - sl_dist if direction == "Long" else entry_price + sl_dist
        tp_price = entry_price + (sl_dist * 2.0) if direction == "Long" else entry_price - (sl_dist * 2.0)

        pos_size = signal.get('position_size', 1.0) # From Kelly (Phase 15)

        entry_time = time.strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades
                (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, slippage_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, "Open", ?)
            ''', (ticker, direction, entry_time, entry_price, sl_price, tp_price, pos_size, cost))
            trade_id = cursor.lastrowid
            conn.commit()

        receipt = {
            "trade_id": trade_id, "ticker": ticker, "direction": direction,
            "net_entry": entry_price, "slippage_paid": cost, "status": "Filled"
        }
        logger.info(f"AUDIT TRAIL: Execution Receipt -> {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl: float, direction: str, current_sl: float) -> bool:
        """Trailing Stop (Strictly Monotonic) & Breakeven Logic (Phase 12)."""
        # Ensure SL only moves in the direction of profit
        if direction == "Long" and new_sl <= current_sl:
            return False
        if direction == "Short" and new_sl >= current_sl:
            return False

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE trades SET sl_price = ? WHERE trade_id = ?', (new_sl, trade_id))
            conn.commit()
            logger.info(f"Trailing Stop updated for Trade ID {trade_id} to {new_sl:.4f}")
            return True

    def close_position(self, trade_id: int, exit_price: float, reason: str) -> bool:
        """Closes position, applies exit slippage, calculates PnL."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ticker, direction, entry_price, position_size
                FROM trades WHERE trade_id = ?
            ''', (trade_id,))
            row = cursor.fetchone()

            if not row: return False
            ticker, direction, entry_price, pos_size = row

            # Exit Slippage Cost
            exit_cost = self.calculate_slippage_and_spread(ticker, 0.01, exit_price) # Placeholder ATR
            net_exit = exit_price - exit_cost if direction == "Long" else exit_price + exit_cost

            # PnL Calculation
            if direction == "Long":
                pnl = (net_exit - entry_price) * pos_size
            else:
                pnl = (entry_price - net_exit) * pos_size

            exit_time = time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                UPDATE trades SET
                status = "Closed", exit_time = ?, exit_price = ?, pnl = ?, reason = ?
                WHERE trade_id = ?
            ''', (exit_time, net_exit, pnl, reason, trade_id))
            conn.commit()

        self.update_balance(pnl)
        logger.info(f"Trade {trade_id} Closed ({reason}). Net Exit: {net_exit:.4f}, PnL: ${pnl:.2f}")
        return True

    def get_closed_trades(self) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query('SELECT * FROM trades WHERE status = "Closed"', conn)
