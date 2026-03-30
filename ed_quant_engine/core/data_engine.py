import yfinance as yf
import pandas as pd
import numpy as np
import time
import asyncio
from typing import Dict, Optional, Tuple
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import feedparser

from .infrastructure import logger
from .config import TICKERS

# Initialize NLTK VADER in memory
try:
    sia = SentimentIntensityAnalyzer()
except LookupError:
    import nltk
    nltk.download('vader_lexicon')
    sia = SentimentIntensityAnalyzer()

class DataEngine:
    def __init__(self, tickers: Dict[str, list]):
        self.tickers = tickers
        # Flatten tickers list
        self.all_tickers = [ticker for category in self.tickers.values() for ticker in category]
        self.macro_tickers = ["DX-Y.NYB", "^TNX", "^VIX"]

    def exponential_backoff(self, func, *args, max_retries=3, base_delay=60, **kwargs):
        """Exponential Backoff logic for API limits."""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Max retries reached for {func.__name__}: {e}")
                    return None
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Error fetching data: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)

    def _fetch_yf_data(self, ticker: str, interval: str, period: str) -> Optional[pd.DataFrame]:
        """Core fetcher using yfinance."""
        data = yf.Ticker(ticker).history(period=period, interval=interval)
        if data.empty:
            logger.warning(f"Empty dataframe returned for {ticker} at {interval}")
            return None

        # Drop columns like Dividends/Stock Splits for clean OHLCV
        cols_to_keep = ["Open", "High", "Low", "Close", "Volume"]
        available_cols = [c for c in cols_to_keep if c in data.columns]
        data = data[available_cols]

        # Phase 2: Handle Missing Data with Forward Fill
        data.ffill(inplace=True)
        data.dropna(inplace=True) # Any remaining NaNs at the beginning

        # Timezone stripping for MTF pandas.merge_asof (Critical Fix)
        if data.index.tzinfo is not None:
            data.index = data.index.tz_localize(None)

        return data

    async def fetch_mtf_data(self, ticker: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Fetch Multi-Timeframe Data (1D for Trend, 1H for Entry)."""
        logger.info(f"Fetching MTF data for {ticker}")

        # Async wrapping for sync yfinance call to prevent blocking the main loop
        loop = asyncio.get_event_loop()

        df_htf = await loop.run_in_executor(
            None,
            lambda: self.exponential_backoff(self._fetch_yf_data, ticker, "1d", "2y")
        )

        df_ltf = await loop.run_in_executor(
            None,
            lambda: self.exponential_backoff(self._fetch_yf_data, ticker, "1h", "1mo")
        )

        return df_htf, df_ltf

    def align_mtf_data(self, df_htf: pd.DataFrame, df_ltf: pd.DataFrame) -> pd.DataFrame:
        """
        Critical Quant Task: MTF Alignment WITHOUT Lookahead Bias (Phase 16).
        We shift the daily (HTF) by 1 BEFORE merging, ensuring the 1H candle
        only sees yesterday's closed daily candle.
        """
        # Shift HTF to simulate "end of previous day"
        df_htf_shifted = df_htf.copy()

        # Calculate daily indicators BEFORE shifting so they represent yesterday's metrics
        # (This will be done in feature engineering, but the shift applies to all HTF columns)

        df_htf_shifted = df_htf_shifted.shift(1)
        df_htf_shifted.dropna(inplace=True)

        # Rename columns to avoid collision
        df_htf_shifted.columns = [f"HTF_{c}" for c in df_htf_shifted.columns]

        # Sort indices just in case
        df_htf_shifted.sort_index(inplace=True)
        df_ltf.sort_index(inplace=True)

        # Merge asof backward: For every hour in LTF, find the most recent previous day in HTF
        aligned_df = pd.merge_asof(
            df_ltf,
            df_htf_shifted,
            left_index=True,
            right_index=True,
            direction='backward'
        )

        return aligned_df

    async def fetch_macro_data(self) -> Dict[str, pd.DataFrame]:
        """Phase 6 & 19: Fetch Macro Filters (DXY, Yields) and Fear Index (VIX)."""
        logger.info("Fetching Macro & VIX Data...")
        macro_dfs = {}
        for ticker in self.macro_tickers:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: self.exponential_backoff(self._fetch_yf_data, ticker, "1d", "1y")
            )
            if df is not None:
                macro_dfs[ticker] = df

        return macro_dfs

class SentimentEngine:
    """Phase 20: NLP VADER Sentiment Analysis via Free RSS Feeds."""

    def __init__(self):
        self.rss_urls = [
            "https://finance.yahoo.com/news/rssindex",
            "https://www.investing.com/rss/news_285.rss" # Commodities
        ]
        self.cache = {}
        self.cache_ttl = 3600 # 1 hour

    async def fetch_sentiment(self, ticker_category: str) -> float:
        """Fetch RSS feeds and analyze sentiment asynchronously."""
        current_time = time.time()
        if ticker_category in self.cache:
            score, timestamp = self.cache[ticker_category]
            if current_time - timestamp < self.cache_ttl:
                return score

        logger.info(f"Fetching RSS News Sentiment for {ticker_category}...")

        keywords = {
            "METALS": ["gold", "silver", "copper", "metal", "mining", "palladium", "platinum"],
            "ENERGY": ["oil", "gas", "crude", "brent", "opec", "energy"],
            "AGRI": ["wheat", "corn", "soybean", "coffee", "sugar", "agriculture", "crop"],
            "FOREX": ["lira", "try", "turkey", "inflation", "cbrt", "fed", "rates", "dollar", "euro"]
        }

        target_keywords = keywords.get(ticker_category, [])
        compound_scores = []

        loop = asyncio.get_event_loop()

        def parse_feeds():
            scores = []
            for url in self.rss_urls:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries:
                        title = entry.title.lower()
                        # If any keyword matches the title
                        if any(kw in title for kw in target_keywords):
                            sentiment = sia.polarity_scores(entry.title)
                            scores.append(sentiment['compound'])
                except Exception as e:
                    logger.warning(f"RSS Feed error on {url}: {e}")
            return scores

        compound_scores = await loop.run_in_executor(None, parse_feeds)

        if not compound_scores:
            final_score = 0.0 # Neutral if no news
        else:
            final_score = sum(compound_scores) / len(compound_scores)

        self.cache[ticker_category] = (final_score, current_time)
        logger.info(f"Sentiment Score for {ticker_category}: {final_score:.3f}")
        return final_score

