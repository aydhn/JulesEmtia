from abc import ABC, abstractmethod
from core.paper_db import PaperDB
from execution.execution_model import calculate_execution_price
import datetime

class BaseBroker(ABC):
    @abstractmethod
    def place_order(self, ticker, direction, price, atr, category, size, sl, tp): pass

class PaperBroker(BaseBroker):
    def __init__(self, db: PaperDB):
        self.db = db

    def place_order(self, ticker, direction, price, atr, category, size, sl, tp):
        exec_price = calculate_execution_price(price, atr, category, direction)

        trade_receipt = {
            "ticker": ticker, "direction": direction,
            "entry_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "entry_price": exec_price, "sl_price": sl, "tp_price": tp,
            "position_size": size, "status": "Open",
            "exit_time": None, "exit_price": None, "pnl": None
        }
        self.db.open_trade(trade_receipt)
        return trade_receipt
