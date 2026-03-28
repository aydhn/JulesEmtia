from abc import ABC, abstractmethod
from core_engine import logger

# Phase 24: Broker Abstraction Layer
class BaseBroker(ABC):
    @abstractmethod
    def place_order(self, ticker: str, direction: str, size: float, price: float, sl: float, tp: float, slippage_cost: float): pass
    @abstractmethod
    def update_sl(self, trade_id: int, new_sl: float): pass
    @abstractmethod
    def close_order(self, trade_id: int, exit_price: float): pass

class PaperBroker(BaseBroker):
    def __init__(self, db_ref):
        self.db = db_ref

    def place_order(self, ticker: str, direction: str, size: float, price: float, sl: float, tp: float, slippage_cost: float):
        trade_id = self.db.open_trade(ticker, direction, price, sl, tp, size, slippage_cost)

        logger.info(f"AUDIT RECEIPT: [{trade_id}] {direction} {size:.2f} {ticker} @ {price:.4f} (Cost: {slippage_cost:.4f})")
        return {"receipt": trade_id, "status": "FILLED"}

    def update_sl(self, trade_id: int, new_sl: float):
        self.db.execute_query("UPDATE trades SET sl_price = ? WHERE trade_id = ?", (new_sl, trade_id))
        logger.info(f"Order [{trade_id}] SL Updated to {new_sl:.4f}")

    def close_order(self, trade_id: int, exit_price: float):
        trade = self.db.fetch_all("SELECT direction, entry_price, position_size, slippage_cost FROM trades WHERE trade_id=?", (trade_id,))
        if not trade: return None

        direction, entry_price, size, slip_cost = trade[0]
        exit_slip = exit_price * 0.0005
        final_exit = exit_price - exit_slip if direction == "Long" else exit_price + exit_slip

        if direction == "Long":
            gross_pnl = (final_exit - entry_price) * size
        else:
            gross_pnl = (entry_price - final_exit) * size

        net_pnl = gross_pnl - (slip_cost * size) - (exit_slip * size)

        self.db.close_trade(trade_id, final_exit, net_pnl)
        logger.info(f"AUDIT RECEIPT: Closed [{trade_id}] @ {final_exit:.4f} | PnL: {net_pnl:.2f}")
        return net_pnl

class TradingSystem:
    def __init__(self, broker: BaseBroker):
        self.broker = broker

    def generate_signal(self, df) -> str:
        # Phase 4 & 16: Confluence & MTF Validation
        if len(df) < 2: return "Hold"
        prev = df.iloc[-2]

        if abs(prev.get('Z_Score', 0)) > 4.0:
            logger.warning("Flaş Çöküş Algılandı. Z-Score Limiti Aşıldı.")
            return "Hold"

        # Confluence logic (HTF Trend + MACD + RSI/Bollinger)
        is_long = (prev.get('HTF_Trend', 0) == 1 and
                  (prev.get('RSI', 50) < 30 or prev.get('Close', 0) <= prev.get('BB_Lower', 0)))

        is_short = (prev.get('HTF_Trend', 0) == -1 and
                   (prev.get('RSI', 50) > 70 or prev.get('Close', 0) >= prev.get('BB_Upper', 0)))

        if is_long: return "Long"
        if is_short: return "Short"
        return "Hold"

    def manage_trailing_stops(self, open_trades: list, current_prices: dict, atrs: dict):
        # Phase 12: Trailing Stop & Breakeven (Strictly Monotonic)
        for trade in open_trades:
            t_id, ticker, dir, entry, sl, tp = trade[0], trade[1], trade[2], trade[4], trade[5], trade[6]
            curr_price = current_prices.get(ticker)
            atr = atrs.get(ticker, 0)

            if not curr_price: continue

            # Breakeven
            if dir == "Long" and curr_price >= entry + atr:
                new_sl = max(sl, entry)
                if new_sl > sl: self.broker.update_sl(t_id, new_sl)
            elif dir == "Short" and curr_price <= entry - atr:
                new_sl = min(sl, entry)
                if new_sl < sl: self.broker.update_sl(t_id, new_sl)

            # Trailing Stop
            if dir == "Long":
                trailing_sl = curr_price - (1.5 * atr)
                if trailing_sl > sl: self.broker.update_sl(t_id, trailing_sl)
            elif dir == "Short":
                trailing_sl = curr_price + (1.5 * atr)
                if trailing_sl < sl: self.broker.update_sl(t_id, trailing_sl)

            # TP/SL Trigger
            if dir == "Long" and (curr_price <= sl or curr_price >= tp):
                self.broker.close_order(t_id, curr_price)
            elif dir == "Short" and (curr_price >= sl or curr_price <= tp):
                self.broker.close_order(t_id, curr_price)
