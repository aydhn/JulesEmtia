import pandas as pd
from typing import Dict, Optional
from .logger import quant_logger

class StrategyEngine:





    @staticmethod
    def check_signals(df: pd.DataFrame) -> Optional[str]:
        """
        Phase 4 & 16: Confluence & MTF Signal Generation.
        We strictly look at the previous closed candle (-2 if currently forming, or -1 if locked).
        Assuming main loop fetches finalized candles via shift logic in features.
        """
        if df.empty or len(df) < 5:
            return None

        # Look at the most recently COMPLETED candle
        last_closed = df.iloc[-1]

        # HTF (Daily) Trend Veto check (If available)
        htf_trend_up = True
        htf_trend_down = True
        if 'EMA_50_HTF' in last_closed:
            htf_trend_up = last_closed['Close_HTF'] > last_closed['EMA_50_HTF']
            htf_trend_down = last_closed['Close_HTF'] < last_closed['EMA_50_HTF']

        # LTF (Hourly) Oscillators
        rsi = last_closed.get('RSI_14', 50)
        macd = last_closed.get('MACDh_12_26_9', 0)
        close = last_closed['Close']
        ema_50 = last_closed.get('EMA_50', close)
        bb_lower = last_closed.get('BBL_20_2.0', 0)
        bb_upper = last_closed.get('BBU_20_2.0', 999999)

        # New LTF Indicators
        adx = last_closed.get('ADX_14', 0)
        stoch_k = last_closed.get('STOCHRSIk_14_14_3_3', 50)
        stoch_d = last_closed.get('STOCHRSId_14_14_3_3', 50)
        bullish_div = last_closed.get('Bullish_Div', False)
        bearish_div = last_closed.get('Bearish_Div', False)

        # We require a trend if ADX is available, e.g. ADX > 20 means there is a trend
        has_trend = adx > 20 if 'ADX_14' in last_closed else True

        # LONG Confluence
        if htf_trend_up and close > ema_50 and has_trend:
            oscillator_long = (rsi < 35 or close <= bb_lower) and macd > 0
            stoch_long = (stoch_k > stoch_d) and (stoch_k < 20)

            if oscillator_long or stoch_long or bullish_div:
                return 'Long'

        # SHORT Confluence
        if htf_trend_down and close < ema_50 and has_trend:
            oscillator_short = (rsi > 65 or close >= bb_upper) and macd < 0
            stoch_short = (stoch_k < stoch_d) and (stoch_k > 80)

            if oscillator_short or stoch_short or bearish_div:
                return 'Short'

        return None



    @staticmethod
    def calculate_dynamic_risk(entry_price: float, atr: float, direction: str) -> tuple[float, float]:
        """Phase 4: Dynamic JP Morgan Risk Mgmt (SL/TP)"""
        if direction == 'Long':
            sl = entry_price - (1.5 * atr)
            tp = entry_price + (3.0 * atr)
        else:
            sl = entry_price + (1.5 * atr)
            tp = entry_price - (3.0 * atr)
        return sl, tp

    @staticmethod
    def check_trade_management(pos: Dict, current_price: float, current_atr: float) -> tuple[str, float]:
        """
        Phase 12: Breakeven & Trailing Stop logic.
        Returns Action ('CLOSE_TP', 'CLOSE_SL', 'UPDATE_SL', 'HOLD') and new value.
        """
        entry = pos['entry_price']
        sl = pos['sl_price']
        tp = pos['tp_price']
        direction = pos['direction']

        # Hit TP or SL?
        if direction == 'Long':
            if current_price >= tp: return 'CLOSE_TP', current_price
            if current_price <= sl: return 'CLOSE_SL', current_price
        else:
            if current_price <= tp: return 'CLOSE_TP', current_price
            if current_price >= sl: return 'CLOSE_SL', current_price

        # Trailing Stop & Breakeven Logic
        if direction == 'Long':
            # Breakeven check
            if current_price >= entry + (1.0 * current_atr) and sl < entry:
                return 'UPDATE_SL', entry

            # Trailing stop check (strictly monotonic)
            new_sl = current_price - (1.5 * current_atr)
            if new_sl > sl:
                return 'UPDATE_SL', new_sl

        else: # Short
            if current_price <= entry - (1.0 * current_atr) and sl > entry:
                return 'UPDATE_SL', entry

            new_sl = current_price + (1.5 * current_atr)
            if new_sl < sl:
                return 'UPDATE_SL', new_sl

        return 'HOLD', 0.0
