from core.logger import get_logger

logger = get_logger()

class StrategyEngine:
    def __init__(self, broker):
        self.broker = broker

    def generate_signal(self, df) -> str:
        if len(df) < 2: return "Hold"
        prev = df.iloc[-2]

        if abs(prev.get('Z_Score', 0)) > 4.0:
            logger.warning("Flaş Çöküş Algılandı. Z-Score Limiti Aşıldı.")
            return "Hold"

        if prev.get('HTF_Trend', 0) == 1 and prev.get('RSI', 50) < 30:
            return "Long"
        elif prev.get('HTF_Trend', 0) == -1 and prev.get('RSI', 50) > 70:
            return "Short"
        return "Hold"

    def manage_trailing_stops(self, open_trades: list, current_prices: dict, atrs: dict):
        for trade in open_trades:
            t_id, ticker, direction, entry, sl, tp = trade[0], trade[1], trade[2], trade[4], trade[5], trade[6]
            curr_price = current_prices.get(ticker)
            atr = atrs.get(ticker, 0)

            if not curr_price: continue

            # Breakeven Logic
            if direction == "Long" and curr_price >= entry + atr:
                new_sl = max(sl, entry)
                if new_sl > sl: self.broker.update_sl(t_id, new_sl)
            elif direction == "Short" and curr_price <= entry - atr:
                new_sl = min(sl, entry)
                if new_sl < sl: self.broker.update_sl(t_id, new_sl)

            # Trailing Stop Logic (Strictly monotonic)
            if direction == "Long":
                trailing_sl = curr_price - (1.5 * atr)
                if trailing_sl > sl: self.broker.update_sl(t_id, trailing_sl)
            elif direction == "Short":
                trailing_sl = curr_price + (1.5 * atr)
                if trailing_sl < sl: self.broker.update_sl(t_id, trailing_sl)

            # TP / SL Triggers
            if direction == "Long" and (curr_price <= sl or curr_price >= tp):
                self.broker.close_order(t_id, curr_price)
            elif direction == "Short" and (curr_price >= sl or curr_price <= tp):
                self.broker.close_order(t_id, curr_price)
