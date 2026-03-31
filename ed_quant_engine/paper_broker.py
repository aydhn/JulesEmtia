import os
from typing import Dict, Any, List
from base_broker import BaseBroker
from paper_db import get_open_positions, open_trade, close_trade, update_sl_price
from logger import setup_logger

logger = setup_logger("PaperBroker")

class PaperBroker(BaseBroker):
    """Concrete implementation of BaseBroker using local SQLite for simulated (paper) trading."""

    def __init__(self):
        self.initial_balance = float(os.getenv("INITIAL_BALANCE", "10000.0"))
        # Balance tracking could be more complex, but for paper trading we sum closed PnLs
        self._balance = self.initial_balance
        logger.info(f"Sanal Broker (PaperBroker) Başlatıldı. Bakiye: {self._balance}")

    def get_account_balance(self) -> float:
        # In a real broker, this is an API call. Here we calculate from db.
        import sqlite3
        conn = sqlite3.connect(os.getenv("DB_NAME", "paper_db.sqlite3"))
        cursor = conn.cursor()
        cursor.execute("SELECT sum(pnl) FROM trades WHERE status = 'Closed'")
        total_pnl = cursor.fetchone()[0] or 0.0
        conn.close()
        return self.initial_balance + total_pnl

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return get_open_positions()

    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float, current_price: float) -> Dict[str, Any]:
        """Simulates placing an order, incorporating estimated slippage and spread (Phase 21)."""

        # Dynamic Spread & Slippage simulation based on asset class
        base_spreads = {
            "GC=F": 0.0002, # 0.02%
            "CL=F": 0.0005, # 0.05%
            "USDTRY=X": 0.0010 # 0.10%
        }

        # Get base spread or default 0.05%
        spread_pct = base_spreads.get(ticker, 0.0005)

        # Simulated Slippage (e.g., 0.05%)
        slippage_pct = 0.0005

        total_cost_pct = (spread_pct / 2) + slippage_pct

        if direction == "Long":
            entry_price = current_price * (1 + total_cost_pct)
        else:
            entry_price = current_price * (1 - total_cost_pct)

        from datetime import datetime
        trade_id = open_trade(
            ticker=ticker,
            direction=direction,
            entry_time=str(datetime.now()),
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            size=size
        )

        receipt = {
            "trade_id": str(trade_id),
            "ticker": ticker,
            "direction": direction,
            "executed_price": entry_price,
            "size": size,
            "slippage_cost": current_price * slippage_pct * size,
            "status": "FILLED"
        }
        logger.info(f"Sanal Emir İletildi (Denetim İzi): {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: str, new_sl: float) -> bool:
        update_sl_price(int(trade_id), new_sl)
        return True

    def close_position(self, trade_id: str, exit_price: float, pnl: float, pnl_percent: float) -> Dict[str, Any]:
        from datetime import datetime
        close_trade(int(trade_id), str(datetime.now()), exit_price, pnl, pnl_percent)
        return {"status": "CLOSED", "exit_price": exit_price, "pnl": pnl}
