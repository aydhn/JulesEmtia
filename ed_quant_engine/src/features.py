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

            # 2. RSI, MACD & Stochastic RSI
            df.ta.rsi(length=14, append=True)
            df.ta.macd(fast=12, slow=26, signal=9, append=True)
            df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)

            # Additional Indicators (ADX)
            df.ta.adx(length=14, append=True)

            # 3. Volatility (ATR & Bollinger Bands)
            df.ta.atr(length=14, append=True)
            df.ta.bbands(length=20, std=2, append=True)

            # 4. Price Action Returns
            df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

            # 5. Divergence Detection (Uyumsuzluk)
            # Find local minimums and maximums for Price and RSI over a 5-period window
            df['Price_Min'] = df['Low'].rolling(window=5, center=True).min()
            df['Price_Max'] = df['High'].rolling(window=5, center=True).max()

            # Using RSI_14 specifically as per pandas_ta naming convention
            if 'RSI_14' in df.columns:
                df['RSI_Min'] = df['RSI_14'].rolling(window=5, center=True).min()
                df['RSI_Max'] = df['RSI_14'].rolling(window=5, center=True).max()

                # Identify if current is a local min/max
                df['Is_Price_Min'] = df['Low'] == df['Price_Min']
                df['Is_RSI_Min'] = df['RSI_14'] == df['RSI_Min']
                df['Is_Price_Max'] = df['High'] == df['Price_Max']
                df['Is_RSI_Max'] = df['RSI_14'] == df['RSI_Max']

                # Bullish Divergence: Price makes lower low, but RSI makes higher low
                # We approximate by checking if price is dropping while RSI is rising over last 5-10 periods
                price_diff = df['Close'].diff(periods=10)
                rsi_diff = df['RSI_14'].diff(periods=10)

                # Bullish Divergence Flag
                df['Bullish_Div'] = (price_diff < 0) & (rsi_diff > 0) & (df['RSI_14'] < 40)

                # Bearish Divergence Flag
                df['Bearish_Div'] = (price_diff > 0) & (rsi_diff < 0) & (df['RSI_14'] > 60)

            # Drop rows with NaN (including the lookback period)
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
