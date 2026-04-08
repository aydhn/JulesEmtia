import pandas as pd
import logging

logger = logging.getLogger(__name__)

class Strategy:
    """
    Phase 4: Confluence Signal Generation
    Phase 16: MTF Approval
    """
    @staticmethod
    def generate_signal(mtf_df: pd.DataFrame) -> dict:
        """Generates signal checking HTF trend and LTF oscillators/divergences."""
        if mtf_df.empty or len(mtf_df) < 2:
            return {}

        # Look at the previous fully closed candle for signals
        prev_candle = mtf_df.iloc[-2]

        # HTF Confirmations (Trend Filter)
        if 'EMA_50_HTF' not in prev_candle or pd.isna(prev_candle['EMA_50_HTF']):
            return {}

        htf_close = prev_candle['Close_HTF']
        htf_ema50 = prev_candle['EMA_50_HTF']
        htf_macd = prev_candle['MACDh_12_26_9_HTF'] if 'MACDh_12_26_9_HTF' in prev_candle else 0

        htf_bullish = htf_close > htf_ema50 and htf_macd > 0
        htf_bearish = htf_close < htf_ema50 and htf_macd < 0

        # LTF Confirmations (Entry Triggers)
        ltf_close = prev_candle['Close']
        ltf_ema50 = prev_candle['EMA_50']
        ltf_rsi = prev_candle.get('RSI_14', 50)
        ltf_macd = prev_candle.get('MACDh_12_26_9', 0)

        # Divergences (If they exist)
        div_bull_rsi = prev_candle.get('Bullish_Div_RSI', False)
        div_bear_rsi = prev_candle.get('Bearish_Div_RSI', False)

        # Base Conditions
        ltf_bull_cond = (ltf_rsi < 35 or ltf_macd > 0 or div_bull_rsi) and ltf_close > ltf_ema50
        ltf_bear_cond = (ltf_rsi > 65 or ltf_macd < 0 or div_bear_rsi) and ltf_close < ltf_ema50

        atr = prev_candle.get('ATR_14', ltf_close * 0.01)

        if htf_bullish and ltf_bull_cond:
            return {"dir": "LONG", "price": ltf_close, "atr": atr}
        elif htf_bearish and ltf_bear_cond:
            return {"dir": "SHORT", "price": ltf_close, "atr": atr}

        return {}
