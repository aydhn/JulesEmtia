from abc import ABC, abstractmethod

class BaseBroker(ABC):
    @abstractmethod
    async def get_account_balance(self): pass

    @abstractmethod
    async def place_order(self, ticker, direction, size, entry_price, sl, tp): pass

    @abstractmethod
    async def modify_trailing_stop(self, trade_id, new_sl): pass

    @abstractmethod
    async def get_open_positions(self): pass

    @abstractmethod
    async def close_position(self, trade_id, exit_price): pass