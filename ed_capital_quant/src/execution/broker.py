from abc import ABC, abstractmethod
from src.core.paper_db import open_trade, close_trade, get_open_trades, update_sl_price
from src.core.logger import logger

class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float, execution_price: float) -> dict:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        pass

    @abstractmethod
    def get_open_positions(self) -> list:
        pass

    @abstractmethod
    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> dict:
        pass

class PaperBroker(BaseBroker):
    def __init__(self, initial_capital: float = 10000.0):
        self._capital = initial_capital

    def get_account_balance(self) -> float:
        # Calculate balance based on closed PnL
        from src.core.paper_db import get_closed_trades
        closed_trades = get_closed_trades()
        total_pnl = sum([t['pnl'] for t in closed_trades if t['pnl'] is not None])
        current_balance = self._capital + total_pnl
        logger.debug(f"Current Balance: {current_balance:.2f}")
        return current_balance

    def place_market_order(self, ticker: str, direction: str, size: float, sl: float, tp: float, execution_price: float) -> dict:
        trade_id = open_trade(ticker, direction, execution_price, sl, tp, size)
        receipt = {
            "trade_id": trade_id,
            "ticker": ticker,
            "direction": direction,
            "size": size,
            "entry_price": execution_price,
            "sl": sl,
            "tp": tp,
            "status": "FILLED"
        }
        logger.info(f"Execution Receipt: {receipt}")
        return receipt

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        update_sl_price(trade_id, new_sl)
        logger.info(f"Trailing Stop updated for Trade #{trade_id} -> {new_sl:.4f}")
        return True

    def get_open_positions(self) -> list:
        return get_open_trades()

    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> dict:
        close_trade(trade_id, exit_price, pnl)
        receipt = {
            "trade_id": trade_id,
            "exit_price": exit_price,
            "pnl": pnl,
            "status": "CLOSED"
        }
        logger.info(f"Position Closed: {receipt}")
        return receipt
