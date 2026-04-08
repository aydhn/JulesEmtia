import pandas as pd
from .quant_models import add_features
from .infrastructure import logger

class Strategy:
    @staticmethod
    def generate_signal(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> dict:
        """Phase 16: Lookahead Bias olmadan Günlük/Saatlik hizalama + Yeni İndikatörler ve Stratejiler"""
        htf_feat = add_features(htf_df)
        ltf_feat = add_features(ltf_df)

        if htf_feat.empty or ltf_feat.empty:
            return None

        # Sızıntıyı önlemek için günlük veri 1 mum kaydırılır
        htf_shifted = htf_feat.shift(1).reset_index()
        ltf_reset = ltf_feat.reset_index()

        if 'Date' not in ltf_reset.columns and 'Datetime' in ltf_reset.columns:
            ltf_reset.rename(columns={'Datetime': 'Date'}, inplace=True)
        if 'Date' not in htf_shifted.columns and 'Datetime' in htf_shifted.columns:
            htf_shifted.rename(columns={'Datetime': 'Date'}, inplace=True)

        merged = pd.merge_asof(ltf_reset, htf_shifted, on='Date', direction='backward', suffixes=('', '_HTF'))

        if merged.empty or len(merged) < 2:
            return None

        last = merged.iloc[-2] # Sinyal kesin kapanmış mumdan alınır
        curr = merged.iloc[-1]['Close']

        # Required columns mapping (checking presence without strict crash if some are missing)
        required_cols = [
            'Close_HTF', 'EMA_50_HTF', 'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'ADX_14'
        ]

        if not all(col in last for col in required_cols):
            logger.debug(f"Missing required columns in strategy for signal generation.")
            return None

        # --- CONFLUENCE RULES (Phase 4 & 16) ---

        # 1. Macro Trend (HTF)
        htf_trend_up = last['Close_HTF'] > last['EMA_50_HTF']
        htf_trend_down = last['Close_HTF'] < last['EMA_50_HTF']

        # Supertrend HTF Check if available
        if 'SUPERTd_7_3.0_HTF' in last:
            htf_trend_up = htf_trend_up and (last['SUPERTd_7_3.0_HTF'] == 1)
            htf_trend_down = htf_trend_down and (last['SUPERTd_7_3.0_HTF'] == -1)

        # 2. Trend Strength
        has_trend = last['ADX_14'] > 20

        # 3. Oscillators & Mean Reversion
        rsi_oversold = last['RSI_14'] < 35
        rsi_overbought = last['RSI_14'] > 65

        mfi_oversold = last.get('MFI_14', 50) < 30
        mfi_overbought = last.get('MFI_14', 50) > 70

        cmf_bull = last.get('CMF_20', 0) > 0.05
        cmf_bear = last.get('CMF_20', 0) < -0.05

        price_at_lower_bb = last['Close'] <= last.get('BBL_20_2.0', 0)
        price_at_upper_bb = last['Close'] >= last.get('BBU_20_2.0', float('inf'))

        stoch_bull_cross = False
        stoch_bear_cross = False
        if 'STOCHRSIk_14_14_3_3' in last and 'STOCHRSId_14_14_3_3' in last:
            stoch_bull_cross = (last['STOCHRSIk_14_14_3_3'] > last['STOCHRSId_14_14_3_3']) and (last['STOCHRSIk_14_14_3_3'] < 20)
            stoch_bear_cross = (last['STOCHRSIk_14_14_3_3'] < last['STOCHRSId_14_14_3_3']) and (last['STOCHRSIk_14_14_3_3'] > 80)

        macd_bull = last['MACDh_12_26_9'] > 0
        macd_bear = last['MACDh_12_26_9'] < 0

        # 4. Divergences
        bull_div_rsi = last.get('Bullish_Div_RSI', False)
        bear_div_rsi = last.get('Bearish_Div_RSI', False)

        bull_div_macd = last.get('Bullish_Div_MACD', False)
        bear_div_macd = last.get('Bearish_Div_MACD', False)

        bull_div_obv = last.get('Bullish_Div_OBV', False)
        bear_div_obv = last.get('Bearish_Div_OBV', False)

        # 5. Supertrend LTF
        supertrend_bull = last.get('SUPERTd_7_3.0', 0) == 1
        supertrend_bear = last.get('SUPERTd_7_3.0', 0) == -1

        # LONG Confluence Strategies
        if htf_trend_up and has_trend:
            # Sub-Strategy 1: Mean Reversion / Oversold Bounce + Money Flow
            strat1 = (rsi_oversold or mfi_oversold or price_at_lower_bb) and macd_bull and cmf_bull

            # Sub-Strategy 2: Divergence confluence
            strat2 = (bull_div_rsi or bull_div_macd or bull_div_obv) and macd_bull

            # Sub-Strategy 3: Pure Trend Following (Supertrend + Stochastic Cross)
            strat3 = supertrend_bull and stoch_bull_cross

            if strat1 or strat2 or strat3:
                return {"dir": "LONG", "price": curr, "atr": last['ATRr_14']}

        # SHORT Confluence Strategies
        if htf_trend_down and has_trend:
            # Sub-Strategy 1: Mean Reversion / Overbought Rejection + Money Flow
            strat1 = (rsi_overbought or mfi_overbought or price_at_upper_bb) and macd_bear and cmf_bear

            # Sub-Strategy 2: Divergence confluence
            strat2 = (bear_div_rsi or bear_div_macd or bear_div_obv) and macd_bear

            # Sub-Strategy 3: Pure Trend Following (Supertrend + Stochastic Cross)
            strat3 = supertrend_bear and stoch_bear_cross

            if strat1 or strat2 or strat3:
                return {"dir": "SHORT", "price": curr, "atr": last['ATRr_14']}

        return None
