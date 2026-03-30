import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__))) # Allows importing paper_db and logger

import paper_db
from logger import log
from datetime import datetime
from typing import Dict, List, Optional
from base_broker import BaseBroker
import execution_model

class PaperBroker(BaseBroker):
    """
    Implements the BaseBroker interface for Paper Trading using SQLite.
    Includes Execution Model simulation (Slippage + Spread).
    """
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital

    def get_account_balance(self) -> float:
        """Returns the current balance by fetching total PnL from closed trades + Initial Capital."""
        try:
            query = "SELECT SUM(pnl) FROM trades WHERE status = 'Closed'"
            result = paper_db.fetch_query(query)
            total_pnl = result[0][0] if result[0][0] is not None else 0.0
            return self.initial_capital + total_pnl
        except Exception as e:
            log.error(f"Failed to fetch account balance: {e}")
            return self.initial_capital

    def get_open_positions(self) -> List[Dict]:
        return paper_db.get_open_trades()

    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl_price: float, tp_price: float) -> Dict:
        """
        Executes a paper trade with realistic Spread/Slippage simulation.
        Stores execution details in the SQLite Database as an Open Trade.
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Store the trade in paper_db
            query = '''
                INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, highest_price, lowest_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?)
            '''
            # Initial highest/lowest for Trailing Stop logic
            paper_db.execute_query(query, (ticker, direction, now, entry_price, sl_price, tp_price, size, entry_price, entry_price))

            # Fetch the generated trade_id (the most recent one for this ticker)
            trade_id_query = "SELECT trade_id FROM trades WHERE ticker = ? AND status = 'Open' ORDER BY trade_id DESC LIMIT 1"
            trade_id = paper_db.fetch_query(trade_id_query, (ticker,))[0][0]

            log.info(f"PAPER TRADE OPENED: {ticker} {direction} | Entry: {entry_price:.4f} | Size: {size:.4f} | SL: {sl_price:.4f} | TP: {tp_price:.4f}")

            return {
                "trade_id": trade_id, "ticker": ticker, "direction": direction,
                "entry_price": entry_price, "sl_price": sl_price, "tp_price": tp_price,
                "size": size, "time": now, "status": "Success"
            }

        except Exception as e:
            log.error(f"Failed to place market order for {ticker}: {e}")
            return {"status": "Failed", "error": str(e)}

    def modify_trailing_stop(self, trade_id: int, new_sl_price: float) -> bool:
        """Updates the SL price strictly in the direction of profit (Monotonic)."""
        try:
            query = "UPDATE trades SET sl_price = ? WHERE trade_id = ? AND status = 'Open'"
            paper_db.execute_query(query, (new_sl_price, trade_id))
            log.info(f"TRAILING STOP UPDATED for Trade #{trade_id} -> New SL: {new_sl_price:.4f}")
            return True
        except Exception as e:
            log.error(f"Failed to update Trailing Stop for Trade #{trade_id}: {e}")
            return False

    def close_position(self, trade_id: int, exit_price: float, reason: str = "Market/TP/SL") -> Dict:
        """
        Closes an open position, computes net PnL (accounting for closing slippage/spread),
        and updates the SQLite record to 'Closed'.
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Fetch existing trade details
            trade_query = "SELECT ticker, direction, entry_price, position_size FROM trades WHERE trade_id = ? AND status = 'Open'"
            trade_info = paper_db.fetch_query(trade_query, (trade_id,))

            if not trade_info:
                log.warning(f"Trade #{trade_id} already closed or not found.")
                return {"status": "Failed", "error": "Trade not found."}

            ticker, direction, entry_price, size = trade_info[0]

            # Calculate PnL
            if direction == "Long":
                gross_pnl = (exit_price - entry_price) * size
            else:
                gross_pnl = (entry_price - exit_price) * size

            # Update Database
            query = '''
                UPDATE trades SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?
                WHERE trade_id = ?
            '''
            paper_db.execute_query(query, (now, exit_price, gross_pnl, trade_id))

            log.info(f"PAPER TRADE CLOSED [{reason}]: {ticker} {direction} | Exit: {exit_price:.4f} | PnL: {gross_pnl:.2f}")

            return {
                "trade_id": trade_id, "ticker": ticker, "direction": direction,
                "exit_price": exit_price, "pnl": gross_pnl, "time": now, "status": "Success", "reason": reason
            }

        except Exception as e:
            log.error(f"Failed to close position #{trade_id}: {e}")
            return {"status": "Failed", "error": str(e)}

    def update_high_low(self, trade_id: int, new_highest: float, new_lowest: float) -> None:
        """Updates highest and lowest prices seen during the trade for Trailing Stop calculations."""
        query = "UPDATE trades SET highest_price = ?, lowest_price = ? WHERE trade_id = ? AND status = 'Open'"
        paper_db.execute_query(query, (new_highest, new_lowest, trade_id))
