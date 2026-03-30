import sqlite3
import config
from base_broker import BaseBroker
from logger import logger
from datetime import datetime
from paper_db import paper_db

class PaperBroker(BaseBroker):
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path

    async def get_account_balance(self):
        # Calculate from initial 10k + total realized PNL
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(pnl) FROM trades WHERE status = 'Closed'")
            result = cur.fetchone()[0]
            total_pnl = result if result else 0.0

        return 10000.0 + total_pnl

    async def place_order(self, ticker, direction, size, entry_price, sl, tp):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''INSERT INTO trades
                (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Open')''',
                (ticker, direction, datetime.now().isoformat(), entry_price, sl, tp, size))
        logger.info(f"Order Placed [PAPER]: {direction} {ticker} at {entry_price:.4f}")

    async def modify_trailing_stop(self, trade_id, new_sl):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))

    async def get_open_positions(self):
        return paper_db.get_open_trades()

    async def close_position(self, trade_id, exit_price):
        # We need the original trade details to calculate PNL correctly
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            trade = conn.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()

        if trade:
            entry_price = trade['entry_price']
            direction = trade['direction']
            size = trade['position_size']

            # Simple PNL (no dynamic exit cost here, should be applied before calling)
            if direction == 'Long':
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size

            paper_db.close_trade(trade_id, exit_price, pnl)
            return pnl
        return 0.0