from abc import ABC, abstractmethod
from typing import Dict, List, Any
import src.paper_db as db
from src.logger import get_logger
from src.execution import ExecutionModel

logger = get_logger()

class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, entry_price: float, sl_price: float, tp_price: float, position_size: float, slippage: float, spread: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, slippage: float, spread: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float, is_breakeven: bool = False):
        pass

    @abstractmethod
    def get_open_positions(self) -> List[Dict[str, Any]]:
        pass


class PaperBroker(BaseBroker):
    def __init__(self):
        db.init_db()
        self.execution_model = ExecutionModel()

    def get_account_balance(self) -> float:
        return db.get_balance()

    def place_market_order(self, ticker: str, direction: str, market_price: float, sl_price: float, tp_price: float, position_size: float, slippage: float = 0.0, spread: float = 0.0, atr: float = 0.0) -> Dict[str, Any]:
        """
        Executes a simulated market order with SPL Level 3 execution receipt audit logs.
        Applies dynamic slippage and spread to the entry price using ExecutionModel.
        """
        if atr == 0.0:
            atr = market_price * 0.01

        dynamic_spread, dynamic_slippage = self.execution_model.calculate_costs(ticker, market_price, atr)

        if direction == "Long":
            execution_price = market_price + (dynamic_spread / 2) + dynamic_slippage
        else:
            execution_price = market_price - (dynamic_spread / 2) - dynamic_slippage

        trade_id = db.open_trade(ticker, direction, execution_price, sl_price, tp_price, position_size)

        receipt = {
            "trade_id": trade_id,
            "ticker": ticker,
            "direction": direction,
            "requested_price": market_price,
            "execution_price": execution_price,
            "slippage_applied": dynamic_slippage,
            "spread_applied": dynamic_spread,
            "position_size": position_size,
            "status": "FILLED"
        }
        logger.info(f"[EXECUTION RECEIPT] {receipt}")
        return receipt

    def close_position(self, trade_id: int, market_price: float, slippage: float = 0.0, spread: float = 0.0, atr: float = 0.0) -> Dict[str, Any]:
        open_trades = db.get_open_trades()
        trade = next((t for t in open_trades if t['trade_id'] == trade_id), None)
        if not trade:
            return {}

        direction = trade['direction']
        ticker = trade['ticker']

        if atr == 0.0:
            atr = market_price * 0.01

        dynamic_spread, dynamic_slippage = self.execution_model.calculate_costs(ticker, market_price, atr)

        if direction == "Long":
            execution_price = market_price - (dynamic_spread / 2) - dynamic_slippage
        else:
            execution_price = market_price + (dynamic_spread / 2) + dynamic_slippage

        result = db.close_trade(trade_id, execution_price)

        receipt = {
            "trade_id": trade_id,
            "requested_price": market_price,
            "execution_price": execution_price,
            "slippage_applied": dynamic_slippage,
            "spread_applied": dynamic_spread,
            "pnl": result.get("pnl", 0.0),
            "status": "CLOSED"
        }
        logger.info(f"[CLOSE RECEIPT] {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl: float, is_breakeven: bool = False):
        db.update_sl_price(trade_id, new_sl, 1 if is_breakeven else 0)

    def get_open_positions(self) -> List[Dict[str, Any]]:
        return db.get_open_trades()
