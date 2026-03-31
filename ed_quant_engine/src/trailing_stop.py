import pandas as pd
from typing import Dict, List
from src.paper_db import db
from src.logger import logger
from src.notifier import send_telegram_message

class TrailingStopManager:
    def __init__(self, atr_multiplier: float = 1.5, breakeven_atr_multiplier: float = 1.0):
        self.atr_multiplier = atr_multiplier
        self.breakeven_atr_multiplier = breakeven_atr_multiplier

    def update_sl_price(self, trade_id: int, new_sl: float):
        query = '''
            UPDATE trades
            SET sl_price = ?
            WHERE trade_id = ?
        '''
        db.cursor.execute(query, (new_sl, trade_id))
        db.conn.commit()

    def manage_trailing_stop(self, current_price: float, atr: float, trade: Dict) -> None:
        """
        Manages Breakeven and dynamic Trailing Stop logic.
        Strictly monotonic: SL only moves in the direction of profit.
        """
        entry_price = float(trade['entry_price'])
        current_sl = float(trade['sl_price'])
        direction = trade['direction']
        ticker = trade['ticker']
        trade_id = trade['trade_id']

        if direction == "Long":
            # 1. Breakeven Logic:
            if current_price >= entry_price + (self.breakeven_atr_multiplier * atr):
                if current_sl < entry_price:
                    self.update_sl_price(trade_id, entry_price)
                    msg = f"🔒 *Risk-Free*: {ticker} SL moved to entry price ({entry_price:.4f})"
                    logger.info(msg)
                    send_telegram_message(msg)
                    return # Exit early after breakeven

            # 2. Dynamic Trailing Stop Logic:
            new_sl = current_price - (self.atr_multiplier * atr)
            if new_sl > current_sl: # Strictly monotonic
                self.update_sl_price(trade_id, new_sl)
                msg = f"🛡️ *Trailing Stop Updated*: {ticker} (Long) SL moved to {new_sl:.4f}"
                logger.info(msg)

        elif direction == "Short":
            # 1. Breakeven Logic:
            if current_price <= entry_price - (self.breakeven_atr_multiplier * atr):
                if current_sl > entry_price:
                    self.update_sl_price(trade_id, entry_price)
                    msg = f"🔒 *Risk-Free*: {ticker} SL moved to entry price ({entry_price:.4f})"
                    logger.info(msg)
                    send_telegram_message(msg)
                    return # Exit early after breakeven

            # 2. Dynamic Trailing Stop Logic:
            new_sl = current_price + (self.atr_multiplier * atr)
            if new_sl < current_sl: # Strictly monotonic
                self.update_sl_price(trade_id, new_sl)
                msg = f"🛡️ *Trailing Stop Updated*: {ticker} (Short) SL moved to {new_sl:.4f}"
                logger.info(msg)
