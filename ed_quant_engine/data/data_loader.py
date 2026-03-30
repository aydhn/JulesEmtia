import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from core.logger import get_logger
from strategy.features import FeaturesEngine

logger = get_logger()

class DataLoader:
    def __init__(self):
        self.feature_engine = FeaturesEngine()

    def fetch_ohlcv(self, ticker: str, interval: str = "1h", period: str = "60d") -> pd.DataFrame:
        """Fetch OHLCV Data with Exponential Backoff."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = yf.download(ticker, interval=interval, period=period, progress=False)
                if df.empty:
                    logger.warning(f"{ticker} verisi boş geldi, tekrar deneniyor ({attempt + 1}).")
                    time.sleep(2 ** attempt)
                    continue

                # Ensure single level columns
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)

                df.ffill(inplace=True)
                df.bfill(inplace=True)
                return df

            except Exception as e:
                logger.error(f"Error fetching data for {ticker}: {e}")
                time.sleep(2 ** attempt)

        logger.critical(f"{ticker} verisi 3 denemede de alınamadı.")
        return pd.DataFrame()

    def fetch_mtf_data(self, ticker: str) -> pd.DataFrame:
        """
        Fetches Daily (HTF) and Hourly (LTF) data, aligns them with ZERO Lookahead Bias.
        Returns the aligned hourly DataFrame enriched with indicators.
        """
        df_ltf = self.fetch_ohlcv(ticker, interval="1h", period="60d")
        df_htf = self.fetch_ohlcv(ticker, interval="1d", period="6mo")

        if df_ltf.empty or df_htf.empty:
            return pd.DataFrame()

        # Calculate indicators for both timeframes
        df_htf = self.feature_engine.add_features(df_htf, is_htf=True)
        df_ltf = self.feature_engine.add_features(df_ltf, is_htf=False)

        # Lookahead Bias Protection: Shift HTF data before merging!
        # This ensures hourly data ONLY sees YESTERDAY'S completely closed daily bar.
        df_htf_shifted = df_htf.shift(1).copy()
        df_htf_shifted = df_htf_shifted.add_prefix('HTF_')
        df_htf_shifted.index = pd.to_datetime(df_htf_shifted.index).tz_localize(None)

        df_ltf.index = pd.to_datetime(df_ltf.index).tz_localize(None)

        # Merge using merge_asof (backward match) to avoid future leaks
        df_combined = pd.merge_asof(
            df_ltf.sort_index(),
            df_htf_shifted.sort_index(),
            left_index=True,
            right_index=True,
            direction='backward'
        )

        df_combined.dropna(inplace=True)
        return df_combined

