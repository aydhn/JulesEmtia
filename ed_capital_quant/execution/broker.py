from abc import ABC, abstractmethod
from core.paper_db import db
from utils.logger import log

class BaseBroker(ABC):
    @abstractmethod
    def place_market_order(self, ticker: str, direction: int, price: float, sl: float, tp: float, size: float):
        pass

class PaperBroker(BaseBroker):
    def place_market_order(self, ticker: str, direction: int, price: float, sl: float, tp: float, size: float):
        log.info(f"Paper Broker Order Execution: {ticker} {direction} @ {price}")
        db.open_trade(ticker, direction, price, sl, tp, size)

broker = PaperBroker()
