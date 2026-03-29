from typing import Dict, List, Any
from datetime import datetime
from ed_quant_engine.broker.broker_base import BaseBroker
from ed_quant_engine.core.paper_db import PaperTradingDB
import ed_quant_engine.config as config
from ed_quant_engine.core.logger import logger

class PaperBroker(BaseBroker):
    """
    Implements BaseBroker using the local SQLite Database (Paper Trading).
    Includes Split Düzey 3 (Audit Trail) and execution cost simulations.
    """
    def __init__(self):
        self.db = PaperTradingDB()

    def get_account_balance(self) -> float:
        return self.db.get_current_capital()

    def place_market_order(self, ticker: str, direction: str, quantity: float, slippage: float, sl_price: float, tp_price: float, current_price: float) -> Dict[str, Any]:
        """
        Simulates execution with dynamic spread and slippage.
        """
        base_spread = 0.0002 # 0.02% basic spread
        if "TRY" in ticker:
            base_spread = 0.0010 # 0.10% spread for exotic pairs

        # Realistic Entry = Price + (Spread/2) + Slippage
        cost_impact = current_price * (base_spread / 2) + slippage

        entry_price = current_price + cost_impact if direction == 'Long' else current_price - cost_impact
        entry_time = datetime.utcnow().isoformat()

        trade_id = self.db.open_trade(
            ticker=ticker,
            direction=direction,
            entry_time=entry_time,
            entry_price=entry_price,
            sl_price=sl_price,
            tp_price=tp_price,
            position_size=quantity
        )

        receipt = {
            "trade_id": trade_id,
            "status": "FILLED",
            "executed_price": entry_price,
            "slippage_paid": slippage,
            "commission": 0.0, # Assumed 0 for paper trade or factored into spread
            "timestamp": entry_time
        }

        logger.info(f"Execution Receipt (SPL Level 3 Audit Trail): {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        self.db.update_sl_price(trade_id, new_sl)
        return True

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return self.db.get_open_trades()

    def close_position(self, trade_id: int, current_price: float, is_sl: bool = False, is_tp: bool = False) -> Dict[str, Any]:
        # Fetch trade first to know direction and entry
        open_trades = self.get_open_positions()
        trade = next((t for t in open_trades if t['trade_id'] == trade_id), None)

        if not trade:
            return {"status": "FAILED", "reason": "Trade not found"}

        direction = trade['direction']
        quantity = trade['position_size']
        entry_price = trade['entry_price']

        # Add exit slippage/spread
        base_spread = 0.0002
        if "TRY" in trade['ticker']:
            base_spread = 0.0010

        cost_impact = current_price * (base_spread / 2)
        exit_price = current_price - cost_impact if direction == 'Long' else current_price + cost_impact

        # Calculate PnL
        if direction == 'Long':
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity

        exit_time = datetime.utcnow().isoformat()

        self.db.close_trade(
            trade_id=trade_id,
            exit_time=exit_time,
            exit_price=exit_price,
            pnl=pnl
        )

        receipt = {
            "trade_id": trade_id,
            "status": "CLOSED",
            "exit_price": exit_price,
            "pnl": pnl,
            "timestamp": exit_time
        }

        logger.info(f"Exit Receipt: {receipt}")
        return receipt
