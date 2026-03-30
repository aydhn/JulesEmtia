import pandas as pd
import pandas_ta as ta
import numpy as np

class FeaturesEngine:
    def add_features(self, df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
        """Calculates indicators for High Timeframe (HTF) and Low Timeframe (LTF)."""
        df = df.copy()

        # Trend & Momentum (HTF is slower, LTF is faster)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)

        if not is_htf:
            df['RSI'] = ta.rsi(df['Close'], length=14)
            df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = ta.macd(df['Close'], fast=12, slow=26, signal=9).T.values
            df['BBL_20_2'], df['BBM_20_2'], df['BBU_20_2'] = ta.bbands(df['Close'], length=20, std=2).iloc[:, :3].T.values

        # Volatility (ATR) - Critical for Stop Loss Calculation
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        # Flash Crash Protection (Z-Score on Price)
        rolling_mean = df['Close'].rolling(window=20).mean()
        rolling_std = df['Close'].rolling(window=20).std()
        df['Z_Score'] = (df['Close'] - rolling_mean) / rolling_std

        # Price Action Returns
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

        df.dropna(inplace=True)
        return df
