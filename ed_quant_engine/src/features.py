import pandas as pd
import pandas_ta as ta
import numpy as np
from .logger import quant_logger

class FeatureEngineer:
    @staticmethod
    def apply_features(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
        """
        Applies strict technical indicators and features.
        is_htf indicates Higher Timeframe (Daily) logic.
        """
        if df is None or len(df) < 200:
            return pd.DataFrame()

        try:
            # 1. Moving Averages
            df.ta.ema(length=50, append=True)
            if is_htf:
                df.ta.ema(length=200, append=True)

            # 2. RSI & MACD
            df.ta.rsi(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)

            # 3. Volatility (ATR & Bollinger Bands)
            df.ta.atr(length=14, append=True)
            df.ta.bbands(length=20, std=2, append=True)

            # 4. Price Action Returns
            df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

            # Avoid Lookahead Bias - we shift everything for signal logic in the strategy
            df.dropna(inplace=True)
            return df
        except Exception as e:
            quant_logger.error(f"Feature engineering failed: {e}")
            return pd.DataFrame()

    @staticmethod
    def align_mtf_data(df_htf: pd.DataFrame, df_ltf: pd.DataFrame) -> pd.DataFrame:
        """
        Align Daily (HTF) features onto Hourly (LTF) dataframe.
        CRITICAL: Shift HTF by 1 BEFORE merge_asof to absolutely prevent Lookahead Bias.
        An hourly candle closing at 14:00 today cannot know today's daily close.
        """
        try:
            # Shift HTF data down by 1 row. Today's hourly uses YESTERDAY'S daily close/features
            htf_shifted = df_htf.shift(1).dropna()

            # Rename columns to identify them
            htf_shifted = htf_shifted.add_suffix('_HTF')

            # Merge using backward direction (match hourly timestamp to the most recent preceding daily timestamp)
            df_ltf_sorted = df_ltf.sort_index()
            htf_shifted_sorted = htf_shifted.sort_index()

            merged = pd.merge_asof(
                df_ltf_sorted,
                htf_shifted_sorted,
                left_index=True,
                right_index=True,
                direction='backward'
            )
            return merged.dropna()
        except Exception as e:
            quant_logger.error(f"MTF alignment failed: {e}")
            return pd.DataFrame()
