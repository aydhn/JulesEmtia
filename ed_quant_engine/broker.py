import os
import datetime
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import paper_db
from execution_model import calculate_slippage_and_spread
from utils.logger import setup_logger

logger = setup_logger("broker")

class BaseBroker(ABC):
    """Abstract Base Class for Broker Abstraction Layer (SOLID)."""

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, qty: float, current_price: float, sl: float, tp: float, atr: float, avg_atr: float = None) -> Optional[int]:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, atr: float, avg_atr: float = None) -> bool:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass


class PaperBroker(BaseBroker):
    """Local simulation broker connected to SQLite."""

    def __init__(self):
        paper_db.init_db()
        logger.info("PaperBroker initialized.")

    def get_account_balance(self) -> float:
        return paper_db.get_balance()

    def place_market_order(
        self,
        ticker: str,
        direction: str,
        qty: float,
        current_price: float,
        sl: float,
        tp: float,
        atr: float,
        avg_atr: float = None
    ) -> Optional[int]:
        """Places an order with SPL Level 3 compatible audit trail logging."""

        # Simulate execution costs (Spread + Slippage)
        execution_cost = calculate_slippage_and_spread(
            ticker=ticker, current_price=current_price, current_atr=atr
        )

        executed_price = current_price + execution_cost if direction == "Long" else current_price - execution_cost

        # Adjust SL and TP based on executed price to maintain Risk/Reward ratios
        # (Simplified: keeping raw SL/TP, but logging the worse entry)

        trade_data = {
            'ticker': ticker,
            'direction': direction,
            'entry_time': datetime.datetime.now().isoformat(),
            'entry_price': executed_price,
            'sl_price': sl,
            'tp_price': tp,
            'position_size': qty
        }

        trade_id = paper_db.open_trade(trade_data)

        # Audit Trail Log
        if trade_id:
            logger.info(
                f"[AUDIT TRAIL] Order Executed | ID: {trade_id} | {direction} {qty} {ticker} | "
                f"Market: {current_price:.4f} | Executed: {executed_price:.4f} | "
                f"Slippage/Spread Cost: ${(abs(executed_price - current_price) * qty):.2f}"
            )

        return trade_id

    def close_position(self, trade_id: int, exit_price: float, atr: float, avg_atr: float = None) -> bool:
        """Closes position, applies execution costs to the exit, calculates PnL."""
        open_trades = self.get_open_positions()
        trade = next((t for t in open_trades if t['trade_id'] == trade_id), None)

        if not trade:
            logger.error(f"Cannot close trade {trade_id}: Not found or already closed.")
            return False

        direction = trade['direction']
        qty = trade['position_size']
        entry_price = trade['entry_price']

        # Reverse direction for closing to calculate costs correctly
        close_direction = "Short" if direction == "Long" else "Long"

        execution_cost = calculate_slippage_and_spread(
            ticker=trade['ticker'], current_price=exit_price, current_atr=atr
        )
        executed_exit_price = exit_price + execution_cost if close_direction == "Long" else exit_price - execution_cost

        # Calculate PnL
        if direction == "Long":
            pnl = (executed_exit_price - entry_price) * qty
        else: # Short
            pnl = (entry_price - executed_exit_price) * qty

        exit_time = datetime.datetime.now().isoformat()
        paper_db.close_trade(trade_id, exit_time, executed_exit_price, pnl)

        logger.info(
            f"[AUDIT TRAIL] Position Closed | ID: {trade_id} | PnL: ${pnl:.2f} | "
            f"Market Exit: {exit_price:.4f} | Executed Exit: {executed_exit_price:.4f}"
        )

        return True

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        """Updates trailing stop strictly monotonic (only in favor of trade)."""
        open_trades = self.get_open_positions()
        trade = next((t for t in open_trades if t['trade_id'] == trade_id), None)

        if not trade:
            return False

        direction = trade['direction']
        current_sl = trade['sl_price']

        # Strictly monotonic check
        if direction == "Long" and new_sl <= current_sl:
            return False # SL can only go up
        if direction == "Short" and new_sl >= current_sl:
            return False # SL can only go down

        paper_db.update_sl_price(trade_id, new_sl)
        return True

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return paper_db.get_open_trades()
