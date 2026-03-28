from abc import ABC, abstractmethod
from core.paper_db import db
from utils.logger import log

class BaseBroker(ABC):
    @abstractmethod
    def place_market_order(self, ticker: str, direction: int, price: float, sl: float, tp: float, size: float):
        pass

class PaperBroker(BaseBroker):
    def place_market_order(self, ticker: str, direction: int, price: float, sl: float, tp: float, size: float):
        # Phase 24: SPL Düzey 3 Audit Trail
        receipt = {
            "type": "MARKET",
            "ticker": ticker,
            "direction": "LONG" if direction == 1 else "SHORT",
            "execution_price": price,
            "sl": sl,
            "tp": tp,
            "size": size,
            "status": "FILLED"
        }
        log.info(f"🧾 Emir İletim Fişi (Execution Receipt): {receipt}")

        # Save to local DB representing the execution
        db.open_trade(ticker, direction, price, sl, tp, size)

# Dependency Injection logic placeholder for real systems (e.g. BinanceBroker)
broker = PaperBroker()
