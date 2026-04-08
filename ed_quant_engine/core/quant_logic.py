import pandas as pd
from .quant_models import add_features

class Strategy:
    @staticmethod
    def generate_signal(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> dict:
        """Phase 16: Lookahead Bias olmadan Günlük/Saatlik hizalama + Yeni İndikatörler"""
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

        required_cols = [
            'Close_HTF', 'EMA_50_HTF', 'RSI_14', 'BBL_20_2.0', 'BBU_20_2.0',
            'MACDh_12_26_9', 'ATRr_14', 'ADX_14', 'STOCHRSIk_14_14_3_3', 'STOCHRSId_14_14_3_3',
            'Bullish_Div', 'Bearish_Div'
        ]

        if not all(col in last for col in required_cols):
            return None

        # --- CONFLUENCE RULES (Phase 4 & 16) ---

        # 1. Macro Trend (HTF)
        htf_trend_up = last['Close_HTF'] > last['EMA_50_HTF']
        htf_trend_down = last['Close_HTF'] < last['EMA_50_HTF']

        # 2. Trend Strength
        has_trend = last['ADX_14'] > 20

        # 3. Oscillators & Mean Reversion
        rsi_oversold = last['RSI_14'] < 35
        rsi_overbought = last['RSI_14'] > 65
        price_at_lower_bb = last['Close'] <= last['BBL_20_2.0']
        price_at_upper_bb = last['Close'] >= last['BBU_20_2.0']

        stoch_bull_cross = (last['STOCHRSIk_14_14_3_3'] > last['STOCHRSId_14_14_3_3']) and (last['STOCHRSIk_14_14_3_3'] < 20)
        stoch_bear_cross = (last['STOCHRSIk_14_14_3_3'] < last['STOCHRSId_14_14_3_3']) and (last['STOCHRSIk_14_14_3_3'] > 80)

        macd_bull = last['MACDh_12_26_9'] > 0
        macd_bear = last['MACDh_12_26_9'] < 0

        # 4. Divergences
        bull_div = last.get('Bullish_Div', False)
        bear_div = last.get('Bearish_Div', False)

        # LONG Confluence
        if htf_trend_up and has_trend:
            # Entry triggers: oversold condition + momentum OR bullish divergence OR stochastic cross
            trigger1 = (rsi_oversold or price_at_lower_bb) and macd_bull
            trigger2 = bull_div and macd_bull
            trigger3 = stoch_bull_cross

            if trigger1 or trigger2 or trigger3:
                return {"dir": "LONG", "price": curr, "atr": last['ATRr_14']}

        # SHORT Confluence
        if htf_trend_down and has_trend:
            # Entry triggers
            trigger1 = (rsi_overbought or price_at_upper_bb) and macd_bear
            trigger2 = bear_div and macd_bear
            trigger3 = stoch_bear_cross

            if trigger1 or trigger2 or trigger3:
                return {"dir": "SHORT", "price": curr, "atr": last['ATRr_14']}

        return None
