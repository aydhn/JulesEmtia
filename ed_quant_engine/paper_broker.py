from base_broker import BaseBroker
import paper_db as db
from config import INITIAL_CAPITAL
from typing import List, Dict, Optional
import datetime
from logger import log

class PaperBroker(BaseBroker):
    """Implementation of BaseBroker using local SQLite for simulated trading."""

    def get_account_balance(self) -> float:
        """Calculate current balance dynamically based on closed trades."""
        trades_df = db.get_all_trades_df()
        if trades_df.empty:
            return INITIAL_CAPITAL

        closed_trades = trades_df[trades_df['status'] == 'Closed']
        if closed_trades.empty:
            return INITIAL_CAPITAL

        total_pnl = closed_trades['pnl'].sum()
        return INITIAL_CAPITAL + total_pnl

    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl: float, tp: float) -> Optional[Dict]:
        """Logs the trade into SQLite and returns the audit receipt."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        query = """
            INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        db.execute_query(query, (ticker, direction, now, entry_price, sl, tp, size, 'Open'))

        log.info(f"PAPER BROKER: Placed {direction} on {ticker} at {entry_price:.4f} (Size: {size:.4f})")

        # Return pseudo-receipt
        return {
            "ticker": ticker,
            "direction": direction,
            "price": entry_price,
            "size": size,
            "timestamp": now,
            "status": "FILLED"
        }

    def close_position(self, trade_id: int, exit_price: float, reason: str = "") -> bool:
        """Closes position in SQLite and calculates PnL."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get trade details
        rows = db.execute_query("SELECT entry_price, direction, position_size FROM trades WHERE trade_id=?", (trade_id,))
        if not rows: return False

        entry_price, direction, size = rows[0]

        # Calculate gross PnL
        if direction == 'Long':
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        # Update DB
        query = "UPDATE trades SET status='Closed', exit_time=?, exit_price=?, pnl=? WHERE trade_id=?"
        db.execute_query(query, (now, exit_price, pnl, trade_id))

        log.info(f"PAPER BROKER: Closed Trade ID {trade_id} at {exit_price:.4f} (PnL: {pnl:.2f}) - Reason: {reason}")
        return True

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> bool:
        """Updates the SL price in SQLite."""
        query = "UPDATE trades SET sl_price=? WHERE trade_id=?"
        db.execute_query(query, (new_sl, trade_id))
        log.info(f"PAPER BROKER: Modified SL for Trade ID {trade_id} to {new_sl:.4f}")
        return True

    def get_open_positions(self) -> List[Dict]:
        """Fetches open trades from SQLite."""
        return db.get_open_trades()
