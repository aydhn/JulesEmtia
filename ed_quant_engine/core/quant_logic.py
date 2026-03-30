import pandas as pd
import pandas_ta as ta

class Strategy:
    @staticmethod
    def add_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Use pandas-ta methods avoiding the warning by calling directly or ensuring columns exist
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.macd(append=True)
        df.ta.atr(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)

        # Mapping pandas-ta dynamic names to expected simple names
        col_map = {
            'EMA_50': 'EMA_50',
            'EMA_200': 'EMA_200',
            'RSI_14': 'RSI_14',
            'MACDh_12_26_9': 'MACD_Hist',
            'ATRr_14': 'ATR',
            'BBL_20_2.0': 'BB_LOWER',
            'BBU_20_2.0': 'BB_UPPER'
        }

        for old_col, new_col in col_map.items():
            if old_col in df.columns:
                df[new_col] = df[old_col]

        return df.dropna()

    @staticmethod
    def generate_signal(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> dict:
        """Phase 16: Lookahead Bias olmadan Günlük/Saatlik hizalama"""
        # Add features BEFORE shifting and merging
        htf_feat = Strategy.add_features(htf_df)
        ltf_feat = Strategy.add_features(ltf_df)

        if htf_feat.empty or ltf_feat.empty:
            return None

        # Sızıntıyı önlemek için günlük veri 1 mum kaydırılır (Gelecek görülmez)
        htf_shifted = htf_feat.shift(1).reset_index()
        ltf_reset = ltf_feat.reset_index()

        # Try finding the Date col or fallback
        if 'Date' not in ltf_reset.columns and 'Datetime' in ltf_reset.columns:
            ltf_reset.rename(columns={'Datetime': 'Date'}, inplace=True)
        if 'Date' not in htf_shifted.columns and 'Datetime' in htf_shifted.columns:
            htf_shifted.rename(columns={'Datetime': 'Date'}, inplace=True)

        merged = pd.merge_asof(ltf_reset, htf_shifted, on='Date', direction='backward', suffixes=('', '_HTF'))

        if merged.empty or len(merged) < 2:
            return None

        last = merged.iloc[-2] # Sinyal kesin kapanmış mumdan alınır!
        curr = merged.iloc[-1]['Close']

        required_cols = ['Close_HTF', 'EMA_50_HTF', 'RSI_14', 'BB_LOWER', 'MACD_Hist', 'BB_UPPER', 'ATR']
        if not all(col in last for col in required_cols):
            return None

        # Long Confluence
        if (last['Close_HTF'] > last['EMA_50_HTF'] and  # Günlük Trend
            (last['RSI_14'] < 30 or last['Close'] <= last['BB_LOWER']) and
            last['MACD_Hist'] > 0):
            return {"dir": "LONG", "price": curr, "atr": last['ATR']}

        # Short Confluence
        if (last['Close_HTF'] < last['EMA_50_HTF'] and
            (last['RSI_14'] > 70 or last['Close'] >= last['BB_UPPER']) and
            last['MACD_Hist'] < 0):
            return {"dir": "SHORT", "price": curr, "atr": last['ATR']}

        return None
