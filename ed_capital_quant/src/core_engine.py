import sqlite3
import pandas as pd
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from config import DB_PATH, BASE_SPREADS, get_asset_class, logger

class DatabaseManager:
    """Manages the local SQLite database for paper trading and state recovery."""
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
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
                status TEXT NOT NULL,
                exit_time TEXT,
                exit_price REAL,
                pnl REAL,
                net_pnl REAL,
                commission REAL,
                slippage REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balance (
                id INTEGER PRIMARY KEY,
                current_balance REAL NOT NULL,
                max_balance REAL NOT NULL,
                last_updated TEXT NOT NULL
            )
        ''')
        conn.commit()
        # Initialize balance if empty
        cursor.execute("SELECT COUNT(*) FROM balance")
        if cursor.fetchone()[0] == 0:
            from config import STARTING_BALANCE
            cursor.execute("INSERT INTO balance (id, current_balance, max_balance, last_updated) VALUES (1, ?, ?, ?)",
                           (STARTING_BALANCE, STARTING_BALANCE, datetime.utcnow().isoformat()))
            conn.commit()
        conn.close()

    def get_balance(self) -> float:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT current_balance FROM balance WHERE id = 1")
        balance = cursor.fetchone()[0]
        conn.close()
        return balance

    def update_balance(self, pnl: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT current_balance, max_balance FROM balance WHERE id = 1")
        current, max_bal = cursor.fetchone()
        new_balance = current + pnl
        new_max = max(new_balance, max_bal)
        cursor.execute("UPDATE balance SET current_balance = ?, max_balance = ?, last_updated = ? WHERE id = 1",
                       (new_balance, new_max, datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def open_trade(self, trade_data: Dict[str, Any]) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, commission, slippage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['ticker'], trade_data['direction'], trade_data['entry_time'],
            trade_data['entry_price'], trade_data['sl_price'], trade_data['tp_price'],
            trade_data['position_size'], 'Open', trade_data.get('commission', 0), trade_data.get('slippage', 0)
        ))
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id

    def close_trade(self, trade_id: int, exit_price: float, net_pnl: float, exit_time: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE trades
            SET status = 'Closed', exit_time = ?, exit_price = ?, net_pnl = ?, pnl = ?
            WHERE trade_id = ?
        ''', (exit_time, exit_price, net_pnl, net_pnl, trade_id)) # using net_pnl for both for simplicity here, but can differentiate gross vs net
        conn.commit()
        conn.close()
        self.update_balance(net_pnl)

    def update_sl(self, trade_id: int, new_sl: float):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
        conn.commit()
        conn.close()

    def get_open_trades(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'Open'", conn)
        conn.close()
        return df

    def get_closed_trades(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed'", conn)
        conn.close()
        return df


class BaseBroker(ABC):
    """Abstract Base Class for SPL Level 3 / Derivative compliant broker execution."""

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, position_size: float, current_atr: float) -> Dict[str, Any]:
        """Places an order, returning an execution receipt with simulated slippage and commission."""
        pass

    @abstractmethod
    def close_position(self, trade_id: int, ticker: str, direction: str, exit_price: float, position_size: float, current_atr: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> pd.DataFrame:
        pass


class PaperBroker(BaseBroker):
    """Local SQLite-backed Paper Trading Broker implementing BaseBroker."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_account_balance(self) -> float:
        return self.db.get_balance()

    def _calculate_execution_costs(self, ticker: str, price: float, current_atr: float, atr_sma: float = None) -> tuple:
        """Calculates dynamic spread and slippage based on ATR."""
        asset_class = get_asset_class(ticker)
        base_spread_pct = BASE_SPREADS.get(asset_class, 0.0010)
        spread_cost = price * base_spread_pct

        # Volatility adjusted slippage
        slippage = 0.0
        if current_atr > 0:
            # Baseline assumption if sma isn't available
            volatility_factor = 1.0
            if atr_sma and current_atr > atr_sma * 1.5:
                volatility_factor = 2.0 # High volatility, double slippage

            # Slippage is modeled as a fraction of ATR (e.g., 5% of ATR) * volatility factor
            slippage = (current_atr * 0.05) * volatility_factor

        return spread_cost, slippage

    def place_market_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, position_size: float, current_atr: float) -> Dict[str, Any]:
        spread, slippage = self._calculate_execution_costs(ticker, price, current_atr)

        # Adjust entry price for execution realism
        if direction == "Long":
            executed_price = price + (spread / 2) + slippage
        else:
            executed_price = price - (spread / 2) - slippage

        commission = position_size * executed_price * 0.0005 # Simulated 0.05% commission

        trade_data = {
            "ticker": ticker,
            "direction": direction,
            "entry_time": datetime.utcnow().isoformat(),
            "entry_price": executed_price,
            "sl_price": sl,
            "tp_price": tp,
            "position_size": position_size,
            "commission": commission,
            "slippage": slippage
        }

        trade_id = self.db.open_trade(trade_data)
        logger.info(f"AUDIT TRAIL: Trade {trade_id} opened. {direction} {ticker} @ {executed_price:.4f}. Slippage: {slippage:.4f}, Comm: {commission:.2f}")

        trade_data['trade_id'] = trade_id
        return trade_data

    def close_position(self, trade_id: int, ticker: str, direction: str, entry_price: float, current_price: float, position_size: float, current_atr: float) -> Dict[str, Any]:
        spread, slippage = self._calculate_execution_costs(ticker, current_price, current_atr)

        if direction == "Long":
            executed_exit_price = current_price - (spread / 2) - slippage
            gross_pnl = (executed_exit_price - entry_price) * position_size
        else:
            executed_exit_price = current_price + (spread / 2) + slippage
            gross_pnl = (entry_price - executed_exit_price) * position_size

        commission = position_size * executed_exit_price * 0.0005
        net_pnl = gross_pnl - commission

        exit_time = datetime.utcnow().isoformat()
        self.db.close_trade(trade_id, executed_exit_price, net_pnl, exit_time)

        logger.info(f"AUDIT TRAIL: Trade {trade_id} closed. Exit @ {executed_exit_price:.4f}. Net PnL: {net_pnl:.2f}. Comm: {commission:.2f}")

        return {
            "trade_id": trade_id,
            "exit_price": executed_exit_price,
            "net_pnl": net_pnl,
            "exit_time": exit_time
        }

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        self.db.update_sl(trade_id, new_sl)
        logger.info(f"AUDIT TRAIL: Trade {trade_id} SL updated to {new_sl:.4f}")
        return True

    def get_open_positions(self) -> pd.DataFrame:
        return self.db.get_open_trades()
