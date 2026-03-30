from abc import ABC, abstractmethod
from core.data_engine import db
from core.config import SPREADS
from system.logger import log

class BaseBroker(ABC):
    @abstractmethod
    def place_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, size: float, category: str):
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, pnl: float):
        pass

class PaperBroker(BaseBroker):
    def place_order(self, ticker: str, direction: str, price: float, sl: float, tp: float, size: float, category: str):
        """Phase 21: Dinamik Spread ve VIX/ATR Kaynaklı Fiyat Kayması (Slippage) Maliyeti"""
        slip = price * (SPREADS.get(category, 0.0005) * 1.5)

        e_p = price + slip if direction == "LONG" else price - slip
        e_sl = sl + slip if direction == "LONG" else sl - slip
        e_tp = tp - slip if direction == "LONG" else tp + slip

        db.open_trade(ticker, direction, e_p, e_sl, e_tp, size)
        log.info(f"AUDIT TRAIL: {direction} {size:.2f} lot {ticker} @ {e_p:.4f} (Maliyet: {slip:.4f})")
        return e_p

    def close_position(self, trade_id: int, exit_price: float, pnl: float):
        # Maliyet eklenebilir, şimdilik sabit
        db.close_trade(trade_id, exit_price, pnl)
        log.info(f"AUDIT TRAIL: Kapatıldı Trade ID {trade_id} @ {exit_price:.4f} (PnL: {pnl:.2f})")
