from abc import ABC, abstractmethod

class BaseBroker(ABC):
    @abstractmethod
    def get_account_balance(self):
        pass

    @abstractmethod
    def place_market_order(self, ticker, direction, size, entry_price, sl, tp, execution_cost):
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id, new_sl):
        pass

    @abstractmethod
    def get_open_positions(self):
        pass

    @abstractmethod
    def close_position(self, trade_id, exit_price, pnl, reason):
        pass
