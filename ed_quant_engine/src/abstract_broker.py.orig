from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from src.paper_db import db
from datetime import datetime
from src.logger import logger

class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict]:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float) -> Optional[int]:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> bool:
        pass

class PaperBroker(BaseBroker):
    """
    Implements the BaseBroker interface using our local SQLite paper_db.
    """
    def __init__(self, initial_balance: float = 10000.0):
        self._initial_balance = initial_balance
        self._balance = initial_balance
        self._update_balance_from_db()

    def _update_balance_from_db(self):
        try:
            # PnL logic: pnl is percentage (0.05). entry_price * position_size = Notional Value.
            # Notional Value * PnL% = Dollar Profit.
            db.cursor.execute("SELECT SUM(pnl * entry_price * position_size) FROM trades WHERE status = 'Closed' AND pnl IS NOT NULL")
            result = db.cursor.fetchone()[0]
            if result is not None:
                 self._balance = self._initial_balance + result
            else:
                 self._balance = self._initial_balance
        except Exception as e:
            logger.error(f"Error calculating balance from DB: {e}")

    def get_account_balance(self) -> float:
        self._update_balance_from_db()
        return self._balance

    def get_open_positions(self) -> List[Dict]:
        return db.get_open_trades()

    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float) -> Optional[int]:
        # Execution Receipt / Audit Trail Logic (Simplified for paper)
        execution_receipt = {
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "direction": direction,
            "executed_price": entry_price, # Assuming slippage already handled
            "size": size,
            "type": "MARKET"
        }
        logger.info(f"AUDIT TRAIL: Execution Receipt generated: {execution_receipt}")

        trade_data = {
            "ticker": ticker,
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "position_size": size,
            "status": "Open"
        }

        return db.open_trade(trade_data)

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        try:
            db.cursor.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
            db.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to modify SL for trade {trade_id}: {e}")
            return False

    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> bool:
         try:
             db.close_trade(trade_id, exit_price, pnl)
             self._update_balance_from_db() # Refresh balance
             return True
         except Exception as e:
             logger.error(f"Failed to close trade {trade_id}: {e}")
             return False
