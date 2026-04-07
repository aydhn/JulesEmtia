from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import uuid
import datetime
from .paper_db import PaperDB
from .config import STARTING_BALANCE
from .logger import quant_logger

class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self) -> float: pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, current_price: float, atr: float, sl: float, tp: float) -> Optional[str]: pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool: pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float) -> bool: pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict]: pass

class PaperBroker(BaseBroker):
    def __init__(self, db: PaperDB):
        self.db = db
        self._cache_balance()

    def _cache_balance(self):
        closed_trades = self.db.get_all_closed_trades_df()
        if closed_trades.empty:
            self.balance = STARTING_BALANCE
        else:
            self.balance = STARTING_BALANCE + closed_trades['net_pnl'].sum()

    def get_account_balance(self) -> float:
        return self.balance

    def _calculate_execution_price(self, current_price: float, atr: float, direction: str) -> float:
        """Phase 21: Dynamic Spread & Slippage Simulation"""
        base_spread_pct = 0.0005 # 0.05% default
        slippage_pct = (atr / current_price) * 0.1 # Dynamic slippage based on ATR

        total_cost_pct = (base_spread_pct / 2) + slippage_pct

        if direction == 'Long':
            return current_price * (1 + total_cost_pct)
        else:
            return current_price * (1 - total_cost_pct)

    def place_market_order(self, ticker: str, direction: str, size: float, current_price: float, atr: float, sl: float, tp: float) -> Optional[str]:
        # Apply Slippage and Spread
        exec_price = self._calculate_execution_price(current_price, atr, direction)

        trade_data = {
            'ticker': ticker,
            'direction': direction,
            'entry_time': datetime.datetime.now().isoformat(),
            'entry_price': exec_price,
            'sl_price': sl,
            'tp_price': tp,
            'position_size': size
        }

        trade_id = self.db.open_trade(trade_data)
        if trade_id != -1:
            # SPL Level 3 Execution Receipt Log
            receipt_id = str(uuid.uuid4())
            quant_logger.info(f"[EXECUTION RECEIPT] ID: {receipt_id} | {direction} {size:.4f} {ticker} @ {exec_price:.4f} (Market: {current_price:.4f})")
            return str(trade_id)
        return None

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        self.db.update_sl_price(trade_id, new_sl)
        return True

    def close_position(self, trade_id: int, exit_price: float, direction: str, entry_price: float, size: float, atr: float) -> bool:
        exec_price = self._calculate_execution_price(exit_price, atr, "Short" if direction == "Long" else "Long")

        if direction == 'Long':
            gross_pnl = (exec_price - entry_price) * size
        else:
            gross_pnl = (entry_price - exec_price) * size

        commission = abs(exec_price * size) * 0.0001 # 0.01% commission
        net_pnl = gross_pnl - commission

        self.db.close_trade(trade_id, datetime.datetime.now().isoformat(), exec_price, gross_pnl, net_pnl)
        self._cache_balance()
        return True

    def get_open_positions(self) -> List[Dict]:
        return self.db.get_open_positions()
