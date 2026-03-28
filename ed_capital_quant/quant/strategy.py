from execution.execution_model import calculate_execution_price
import pandas as pd

class StrategyEngine:
    @staticmethod
    def check_signal(df: pd.DataFrame):
        if len(df) < 2: return None
        last = df.iloc[-1]
        prev = df.iloc[-2]

        try:
            long_cond = (
                (last.get('D1_Close', 0) > last.get('D1_EMA_50', 0)) and
                (last.get('MACD_12_26_9', 0) > last.get('MACDs_12_26_9', 0)) and
                (prev.get('MACD_12_26_9', 0) <= prev.get('MACDs_12_26_9', 0))
            )

            short_cond = (
                (last.get('D1_Close', 0) < last.get('D1_EMA_50', 0)) and
                (last.get('MACD_12_26_9', 0) < last.get('MACDs_12_26_9', 0)) and
                (prev.get('MACD_12_26_9', 0) >= prev.get('MACDs_12_26_9', 0))
            )

            if long_cond: return "Long"
            if short_cond: return "Short"
        except:
            pass
        return None

    @staticmethod
    def calculate_dynamic_risk(price: float, atr: float, direction: str):
        if direction == "Long":
            return price - (1.5 * atr), price + (3.0 * atr)
        else:
            return price + (1.5 * atr), price - (3.0 * atr)

    @staticmethod
    def manage_trailing_stop(trade: dict, current_price: float, atr: float) -> float:
        new_sl = trade['sl_price']
        entry = trade['entry_price']

        if trade['direction'] == "Long":
            if current_price >= entry + (1.0 * atr) and new_sl < entry:
                new_sl = entry
            if current_price - (1.5 * atr) > new_sl:
                new_sl = current_price - (1.5 * atr)
        else:
            if current_price <= entry - (1.0 * atr) and new_sl > entry:
                new_sl = entry
            if current_price + (1.5 * atr) < new_sl:
                new_sl = current_price + (1.5 * atr)

        return new_sl
