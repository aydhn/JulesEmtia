from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

from .infrastructure import logger, PaperDB

class BaseBroker(ABC):
    """Phase 24: Broker Soyutlama Katmanı (Abstract Base Class)."""
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
    """Phase 24: Sanal Broker ve SPL Düzey 3 Emir İletim Fişi."""
    def __init__(self, db: PaperDB):
        self.db = db

    def get_account_balance(self) -> float:
        return self.db.get_balance()

    def get_open_positions(self) -> pd.DataFrame:
        return self.db.get_open_trades()

    def place_market_order(self, ticker: str, direction: str, lot_size: float, sl_price: float, tp_price: float, current_price: float, spread_cost: float, slippage_cost: float) -> Dict[str, Any]:
        """Phase 21: Maliyetli Giriş Simülasyonu ve SPL Düzey 3 Denetim İzi."""

        if direction == "LONG":
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

            # SPL Level 3 Execution Receipt (Audit Trail)
            logger.info(f"AUDIT TRAIL: Execution Receipt - ID: {trade_id} | {direction} {lot_size:.4f} lots {ticker} @ {entry_price:.4f} (Spread: {spread_cost:.5f}, Slippage: {slippage_cost:.5f})")

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

        logger.info(f"AUDIT TRAIL: Close Receipt - ID: {trade_id} closed at {exit_price:.4f} | PnL: {pnl:.2f} | New Balance: {new_balance:.2f}")
        return True
