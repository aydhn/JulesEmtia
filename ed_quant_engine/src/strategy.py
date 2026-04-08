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

        # Determine column name robustly
        htf_macd_col = [c for c in mtf_df.columns if c.startswith('MACDh_') and c.endswith('_HTF')]
        htf_macd = prev_candle[htf_macd_col[0]] if htf_macd_col else 0

        htf_bullish = htf_close > htf_ema50 and htf_macd > 0
        htf_bearish = htf_close < htf_ema50 and htf_macd < 0

        # LTF Confirmations (Entry Triggers)
        ltf_close = prev_candle['Close']
        ltf_ema50 = prev_candle['EMA_50']

        # Ensure column exists for RSI and MACD
        rsi_col = [c for c in mtf_df.columns if c.startswith('RSI_')]
        ltf_rsi = prev_candle[rsi_col[0]] if rsi_col else 50

        ltf_macd_col = [c for c in mtf_df.columns if c.startswith('MACDh_') and not c.endswith('_HTF')]
        ltf_macd = prev_candle[ltf_macd_col[0]] if ltf_macd_col else 0

        # Extract Stoch
        stoch_k_col = [c for c in mtf_df.columns if c.startswith('STOCHk_') and not c.endswith('_HTF')]
        stoch_k = prev_candle[stoch_k_col[0]] if stoch_k_col else 50

        # Extract OBV and check trend
        obv_col = [c for c in mtf_df.columns if c.startswith('OBV') and not c.endswith('_HTF')]
        obv = prev_candle[obv_col[0]] if obv_col else 0

        # Check if OBV is trending up/down using a simple assumption (we can't easily get previous candle's OBV from prev_candle, so we will do a basic check or just pass if not available)
        # Actually, since prev_candle is a row, we can check if OBV is > 0, but usually OBV is cumulative. To check trend we need `mtf_df['OBV'].diff()`.
        obv_trend_up = True
        obv_trend_down = True
        if obv_col and len(mtf_df) >= 3:
            prev_obv = mtf_df.iloc[-3][obv_col[0]]
            obv_trend_up = obv > prev_obv
            obv_trend_down = obv < prev_obv

        # Divergences (If they exist)
        div_bull_rsi = prev_candle.get('Bullish_Div_RSI', False)
        div_bear_rsi = prev_candle.get('Bearish_Div_RSI', False)

        div_bull_stoch = prev_candle.get('Bullish_Div_Stoch', False)
        div_bear_stoch = prev_candle.get('Bearish_Div_Stoch', False)

        div_bull_macd = prev_candle.get('Bullish_Div_MACD', False)
        div_bear_macd = prev_candle.get('Bearish_Div_MACD', False)

        # Base Conditions with Confluence
        # Extract new indicators
        mfi_col = [c for c in mtf_df.columns if c.startswith('MFI_')]
        ltf_mfi = prev_candle[mfi_col[0]] if mfi_col else 50

        cmf_col = [c for c in mtf_df.columns if c.startswith('CMF_')]
        ltf_cmf = prev_candle[cmf_col[0]] if cmf_col else 0

        # SUPERTd contains direction (1 for bullish, -1 for bearish)
        super_col = [c for c in mtf_df.columns if c.startswith('SUPERTd_')]
        ltf_supertrend_dir = prev_candle[super_col[0]] if super_col else 0

        div_bull_mfi = prev_candle.get('Bullish_Div_MFI', False)
        div_bear_mfi = prev_candle.get('Bearish_Div_MFI', False)

        # Long requires: (RSI oversold OR MACD positive OR Stochastic oversold OR MFI oversold OR any bullish divergence) AND OBV trend up AND Close > EMA50 AND Supertrend Bullish AND CMF > 0
        ltf_bull_cond = (
            (ltf_rsi < 35 or ltf_macd > 0 or stoch_k < 20 or ltf_mfi < 35 or div_bull_rsi or div_bull_stoch or div_bull_macd or div_bull_mfi)
            and obv_trend_up
            and (ltf_close > ltf_ema50)
            and (ltf_supertrend_dir == 1 or not super_col)
            and (ltf_cmf > 0 or not cmf_col)
        )

        # Short requires: (RSI overbought OR MACD negative OR Stochastic overbought OR MFI overbought OR any bearish divergence) AND OBV trend down AND Close < EMA50 AND Supertrend Bearish AND CMF < 0
        ltf_bear_cond = (
            (ltf_rsi > 65 or ltf_macd < 0 or stoch_k > 80 or ltf_mfi > 65 or div_bear_rsi or div_bear_stoch or div_bear_macd or div_bear_mfi)
            and obv_trend_down
            and (ltf_close < ltf_ema50)
            and (ltf_supertrend_dir == -1 or not super_col)
            and (ltf_cmf < 0 or not cmf_col)
        )


        atr_col = [c for c in mtf_df.columns if c.startswith('ATR_')]
        atr = prev_candle[atr_col[0]] if atr_col else ltf_close * 0.01

        if htf_bullish and ltf_bull_cond:
            return {"dir": "LONG", "price": ltf_close, "atr": atr}
        elif htf_bearish and ltf_bear_cond:
            return {"dir": "SHORT", "price": ltf_close, "atr": atr}

        return {}
