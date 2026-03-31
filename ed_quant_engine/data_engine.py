import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import time
from typing import Dict, Any, Tuple
from logger import get_logger
from sentiment_engine import SentimentAnalyzer
import asyncio

logger = get_logger("data_engine")
sentiment_analyzer = SentimentAnalyzer()

class DataEngine:
    """
    Core data engine handling OHLCV ingestion, feature engineering,
    and MTF (Multi-Timeframe) merging with strict lookahead bias prevention.
    """

    def __init__(self):
        self.cache = {}

    def _fetch_data_with_retry(self, ticker: str, interval: str, period: str, retries: int = 3) -> pd.DataFrame:
        """Exponential backoff data fetcher from yfinance."""
        for attempt in range(retries):
            try:
                df = yf.download(ticker, interval=interval, period=period, progress=False)
                if not df.empty:
                    # Clean up multi-index columns if present (yfinance 0.2.x quirk)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel(1)
                    return df
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Failed to fetch {ticker} ({interval}). Retrying in {wait}s... ({e})")
                time.sleep(wait)
        logger.error(f"Max retries reached for {ticker} ({interval}).")
        return pd.DataFrame()

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adds vectorized technical indicators to the DataFrame."""
        if df.empty or len(df) < 200:
            return df

        # Ensure we are using pandas_ta
        # Trend
        df.ta.ema(length=50, append=True)
        df.ta.ema(length=200, append=True)

        # Momentum
        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)

        # Volatility
        df.ta.atr(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)

        # Z-Score for Flash Crash Anomaly Detection
        df['Z_SCORE'] = (df['Close'] - df['Close'].rolling(window=50).mean()) / df['Close'].rolling(window=50).std()

        # Clean NaNs (Lookback periods)
        df.dropna(inplace=True)
        return df

    async def get_mtf_data(self, ticker: str) -> pd.DataFrame:
        """
        Fetches 1D and 1H data, computes indicators, and merges them
        preventing lookahead bias (using shift on higher timeframe).
        """
        # Run synchronous blocking IO in thread pool
        htf_df = await asyncio.to_thread(self._fetch_data_with_retry, ticker, "1d", "2y")
        ltf_df = await asyncio.to_thread(self._fetch_data_with_retry, ticker, "1h", "60d")

        if htf_df.empty or ltf_df.empty:
            return pd.DataFrame()

        # Add indicators on HTF *before* merging
        htf_df = self.add_indicators(htf_df)

        # Shift HTF by 1 to strictly prevent lookahead bias!
        # When merging on 1H (e.g., 2023-10-10 14:00), we must only know the HTF
        # data that was available at 2023-10-09 23:59:59.
        htf_shifted = htf_df.shift(1)

        # Rename columns to avoid collision
        htf_shifted.columns = [f"HTF_{c}" for c in htf_shifted.columns]

        # Add indicators on LTF
        ltf_df = self.add_indicators(ltf_df)

        # Strip timezones for merging
        if ltf_df.index.tz is not None:
            ltf_df.index = ltf_df.index.tz_localize(None)
        if htf_shifted.index.tz is not None:
            htf_shifted.index = htf_shifted.index.tz_localize(None)

        # Merge Asof: For every hour in LTF, find the most recent (backward) daily row in shifted HTF
        merged_df = pd.merge_asof(
            ltf_df.sort_index(),
            htf_shifted.sort_index(),
            left_index=True,
            right_index=True,
            direction='backward'
        )

        # Drop rows where HTF data wasn't available yet
        merged_df.dropna(inplace=True)

        # Fetch News Sentiment (Caching can be implemented here, simplified for now)
        sentiment_keywords = [ticker.split('=')[0], "Gold", "Silver", "Oil", "Forex", "USD"]
        sentiment_score = await asyncio.to_thread(sentiment_analyzer.get_market_sentiment, sentiment_keywords)
        merged_df['SENTIMENT_SCORE'] = sentiment_score

        return merged_df
