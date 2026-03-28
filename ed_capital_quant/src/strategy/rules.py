import pandas as pd
import numpy as np
from src.core.logger import logger

class TradingRules:
    @staticmethod
    def generate_signal(df: pd.DataFrame) -> dict:
        """
        Vectorized Multi-Timeframe Confluence Signal Generation.
        df must contain aligned HTF and LTF columns.
        """
        try:
            # We strictly look at the previous closed bar (shift(1))
            prev = df.iloc[-2] if len(df) > 1 else df.iloc[-1]

            # Extract indicators
            close = prev['Close']
            ema50 = prev['EMA_50']
            rsi14 = prev['RSI_14']
            macd = prev['MACD_12_26_9']
            macds = prev['MACDs_12_26_9']
            atr = prev['ATR_14']
            bbl = prev['BBL_20_2.0']
            bbu = prev['BBU_20_2.0']

            # HTF Indicators (Must be present from align_mtf_data)
            htf_close = prev.get('HTF_Close', close)
            htf_ema50 = prev.get('HTF_EMA_50', ema50)
            htf_macd = prev.get('HTF_MACD_12_26_9', macd)
            htf_macds = prev.get('HTF_MACDs_12_26_9', macds)

            # Long Setup
            # 1. HTF Trend Up (Master Veto)
            htf_trend_up = (htf_close > htf_ema50) and (htf_macd > htf_macds)

            # 2. LTF Entry Confluence
            ltf_long_entry = (close > ema50) and ((rsi14 < 40) or (close <= bbl)) and (macd > macds)

            if htf_trend_up and ltf_long_entry:
                sl = close - (1.5 * atr)
                tp = close + (3.0 * atr)
                return {"signal": 1, "direction": "Long", "sl": sl, "tp": tp, "atr": atr}

            # Short Setup
            # 1. HTF Trend Down (Master Veto)
            htf_trend_down = (htf_close < htf_ema50) and (htf_macd < htf_macds)

            # 2. LTF Entry Confluence
            ltf_short_entry = (close < ema50) and ((rsi14 > 60) or (close >= bbu)) and (macd < macds)

            if htf_trend_down and ltf_short_entry:
                sl = close + (1.5 * atr)
                tp = close - (3.0 * atr)
                return {"signal": -1, "direction": "Short", "sl": sl, "tp": tp, "atr": atr}

            return {"signal": 0}
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            return {"signal": 0}

    @staticmethod
    def calculate_trailing_stop(direction: str, current_price: float, current_sl: float, entry_price: float, atr: float) -> float:
        """
        ATR-based Trailing Stop & Breakeven logic. Strictly monotonic (only moves in favor of profit).
        """
        new_sl = current_sl

        if direction == "Long":
            # Breakeven check: If profit is > 1.0 ATR, move SL to Entry Price
            if current_price >= entry_price + (1.0 * atr) and current_sl < entry_price:
                new_sl = entry_price
                logger.info("SL moved to Breakeven (Long)")

            # Trailing Stop calculation
            potential_sl = current_price - (1.5 * atr)
            if potential_sl > new_sl: # Strictly monotonic
                new_sl = potential_sl

        elif direction == "Short":
            # Breakeven check
            if current_price <= entry_price - (1.0 * atr) and current_sl > entry_price:
                new_sl = entry_price
                logger.info("SL moved to Breakeven (Short)")

            # Trailing Stop calculation
            potential_sl = current_price + (1.5 * atr)
            if potential_sl < new_sl: # Strictly monotonic
                new_sl = potential_sl

        return new_sl
