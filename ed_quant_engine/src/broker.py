import abc
from typing import Dict, List
import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BaseBroker(abc.ABC):
    """
    Phase 24: Broker Abstraction Layer & SPL Level 3 Execution Architecture.
    """
    @abc.abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abc.abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float, spread: float, slippage: float) -> Dict:
        pass

    @abc.abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        pass

    @abc.abstractmethod
    def close_position(self, trade_id: int, exit_price: float, slippage_cost: float = 0.0) -> Dict:
        pass

    @abc.abstractmethod
    def get_open_positions(self) -> List[Dict]:
        pass


class PaperBroker(BaseBroker):
    def __init__(self, db_path: str = "paper_db.sqlite3", initial_capital: float = 10000.0):
        self.db_path = db_path
        self.initial_capital = initial_capital
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                pnl REAL,
                execution_cost REAL,
                highest_price REAL,
                lowest_price REAL
            )
        ''')
        conn.commit()
        conn.close()

    def get_account_balance(self) -> float:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(pnl) FROM trades WHERE status = 'Closed'")
        res = cursor.fetchone()[0]
        conn.close()
        return self.initial_capital + (res if res else 0.0)

    def get_open_positions(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE status = 'Open'")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float, spread: float, slippage: float) -> Dict:
        """SPL Level 3 Audit Trail Execution."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Phase 21: Exact cost simulation
        executed_price = entry_price + (spread/2) + slippage if direction == "LONG" else entry_price - (spread/2) - slippage
        exec_cost = (spread/2 + slippage) * size

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, highest_price, lowest_price, execution_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)
        ''', (ticker, direction, now, executed_price, sl_price, tp_price, size, executed_price, executed_price, exec_cost))
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        receipt = {
            "trade_id": trade_id, "ticker": ticker, "direction": direction,
            "executed_price": executed_price, "cost": exec_cost, "time": now
        }
        logger.info(f"AUDIT LOG: Order Executed -> {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ? AND status = 'Open'", (new_sl_price, trade_id))
        conn.commit()
        conn.close()
        logger.info(f"Trailing Stop updated for Trade #{trade_id} -> {new_sl_price:.4f}")
        return True

    def close_position(self, trade_id: int, exit_price: float, slippage_cost: float = 0.0) -> Dict:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT direction, entry_price, position_size, execution_cost FROM trades WHERE trade_id = ? AND status = 'Open'", (trade_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {}

        direction, entry_price, size, exec_cost = row

        # Calculate PnL (Net of execution costs)
        gross_pnl = (exit_price - entry_price) * size if direction == "LONG" else (entry_price - exit_price) * size
        net_pnl = gross_pnl - exec_cost - (slippage_cost * size)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE trades SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ? WHERE trade_id = ?",
                      (now, exit_price, net_pnl, trade_id))
        conn.commit()
        conn.close()

        logger.info(f"Position Closed: Trade #{trade_id} -> Net PnL: {net_pnl:.2f}")
        return {"trade_id": trade_id, "pnl": net_pnl}
