import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import logging
import asyncio

from config import logger, UNIVERSE, HTF_INTERVAL, LTF_INTERVAL, VIX_PANIC_THRESHOLD

# Ensure NLTK VADER lexicon is downloaded (can be done once during setup)
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class DataLoader:
    """Handles fetching historical OHLCV data with robust error handling and Multi-Timeframe support."""
    def __init__(self, tickers: List[str] = None):
        self.tickers = []
        if tickers is None:
            for v in UNIVERSE.values():
                self.tickers.extend(v)
        else:
            self.tickers = tickers

    def _fetch_yf_data(self, ticker: str, interval: str, period: str = "2y") -> pd.DataFrame:
        """Fetches data for a single ticker with exponential backoff."""
        max_retries = 3
        delay = 1

        for attempt in range(max_retries):
            try:
                df = yf.download(ticker, period=period, interval=interval, progress=False, timeout=10)

                if df.empty:
                    logger.warning(f"No data returned for {ticker} at {interval}.")
                    return pd.DataFrame()

                # Clean MultiIndex columns if yfinance returns them
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)

                # Forward fill NaNs (weekends, missing ticks) and drop remaining
                df = df.ffill().dropna()

                # Standardize column names
                df.columns = [c.lower() for c in df.columns]

                if not {'open', 'high', 'low', 'close', 'volume'}.issubset(df.columns):
                    logger.error(f"Missing required OHLCV columns for {ticker}")
                    return pd.DataFrame()

                return df

            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {ticker} ({interval}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch {ticker} after {max_retries} attempts.")
                    return pd.DataFrame()

                import time
                time.sleep(delay)
                delay *= 2  # Exponential backoff

        return pd.DataFrame()

    async def fetch_mtf_data(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Asynchronously fetches both Daily (HTF) and Hourly (LTF) data for the universe."""
        data_dict = {}

        for ticker in self.tickers:
            logger.info(f"Fetching MTF data for {ticker}")
            # In a real async environment, we'd use aiohttp or wrap yf.download in run_in_executor
            # For simplicity in this script, we'll fetch sequentially but structure for async orchestrator
            htf_df = self._fetch_yf_data(ticker, interval=HTF_INTERVAL, period="5y")
            ltf_df = self._fetch_yf_data(ticker, interval=LTF_INTERVAL, period="2y") # yf limits 1h to 730 days max

            if not htf_df.empty and not ltf_df.empty:
                data_dict[ticker] = {
                    "htf": htf_df,
                    "ltf": ltf_df
                }
            # Respect rate limits
            await asyncio.sleep(0.5)

        return data_dict


class FeatureEngineer:
    """Calculates technical indicators ensuring zero lookahead bias and aligns MTF data."""

    @staticmethod
    def add_features(df: pd.DataFrame) -> pd.DataFrame:
        """Adds core technical indicators using pandas_ta."""
        if df.empty or len(df) < 200:
            return df

        # Trend Filter
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['ema_200'] = ta.ema(df['close'], length=200)

        # Momentum & Overbought/Oversold
        df['rsi_14'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'])
        if macd is not None:
            df = df.join(macd)
            df.rename(columns={'MACD_12_26_9': 'macd', 'MACDhist_12_26_9': 'macd_hist', 'MACDs_12_26_9': 'macd_signal'}, inplace=True)

        # Volatility & Risk Management
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        if atr is not None:
            df['atr_14'] = atr
            df['atr_sma'] = ta.sma(df['atr_14'], length=50) # for slippage modeling

        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None:
             df = df.join(bbands)
             df.rename(columns={'BBL_20_2.0': 'bb_lower', 'BBU_20_2.0': 'bb_upper'}, inplace=True)

        # Price Action (Log returns)
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))

        # Shift all features to avoid lookahead bias!
        # The signal for time t must only use data available up to time t-1
        shifted_cols = [c for c in df.columns if c not in ['open', 'high', 'low', 'close', 'volume']]
        for col in shifted_cols:
             df[f"{col}_prev"] = df[col].shift(1)

        return df.dropna()

    @staticmethod
    def align_mtf(ltf_df: pd.DataFrame, htf_df: pd.DataFrame) -> pd.DataFrame:
        """
        Aligns Daily (HTF) data to Hourly (LTF) DataFrame.
        CRITICAL: Prevents Lookahead Bias by only taking the LAST CLOSED daily candle.
        """
        if ltf_df.empty or htf_df.empty:
            return pd.DataFrame()

        # Ensure indices are timezone-aware if one is and the other isn't, or both naive
        if ltf_df.index.tz is None and htf_df.index.tz is not None:
            ltf_df.index = ltf_df.index.tz_localize('UTC')
        elif ltf_df.index.tz is not None and htf_df.index.tz is None:
            htf_df.index = htf_df.index.tz_localize('UTC')

        # We shift HTF by 1 so that the value on day T is the CLOSE of day T-1
        # Then we merge_asof backward so hour 14:00 on day T gets day T-1's daily close
        htf_shifted = htf_df.copy()

        # Shift data
        cols_to_shift = [c for c in htf_shifted.columns if c not in ['open', 'high', 'low', 'close', 'volume']]

        # We need the actual HTF close to compute things like "is current LTF close > HTF EMA"
        htf_shifted['htf_close_prev'] = htf_shifted['close'].shift(1)
        for col in cols_to_shift:
             htf_shifted[f"htf_{col}_prev"] = htf_shifted[col].shift(1)

        # Keep only shifted columns + datetime index
        htf_shifted = htf_shifted[[c for c in htf_shifted.columns if 'htf_' in c]]
        htf_shifted = htf_shifted.dropna()

        # Sort indices required for merge_asof
        ltf_df = ltf_df.sort_index()
        htf_shifted = htf_shifted.sort_index()

        try:
             merged = pd.merge_asof(ltf_df, htf_shifted, left_index=True, right_index=True, direction='backward')
             return merged
        except Exception as e:
             logger.error(f"MTF Alignment failed: {e}")
             return ltf_df


class MacroRegimeFilter:
    """Monitors Macro environment (VIX, DXY, TNX) for circuit breakers and trend vetoes."""

    @staticmethod
    def get_macro_data() -> Dict[str, pd.DataFrame]:
        logger.info("Fetching Macro Regime Data...")
        macro_data = {}
        for ticker in UNIVERSE["Macro"]:
            try:
                df = yf.download(ticker, period="1mo", interval="1d", progress=False)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel(1)
                df = df.ffill().dropna()
                df.columns = [c.lower() for c in df.columns]
                if not df.empty:
                    macro_data[ticker] = df
            except Exception as e:
                logger.error(f"Failed to fetch macro data for {ticker}: {e}")
        return macro_data

    @staticmethod
    def check_vix_circuit_breaker(macro_data: Dict[str, pd.DataFrame]) -> bool:
        """Returns True if VIX indicates a Black Swan/Panic event. System halts."""
        vix_ticker = "^VIX"
        if vix_ticker in macro_data and not macro_data[vix_ticker].empty:
             last_vix_close = macro_data[vix_ticker]['close'].iloc[-1]
             # Check if VIX is above threshold OR spiked > 20% in a day
             if last_vix_close >= VIX_PANIC_THRESHOLD:
                 logger.critical(f"VIX CIRCUIT BREAKER TRIPPED! VIX at {last_vix_close:.2f} >= {VIX_PANIC_THRESHOLD}")
                 return True

             if len(macro_data[vix_ticker]) > 1:
                 prev_vix_close = macro_data[vix_ticker]['close'].iloc[-2]
                 pct_change = (last_vix_close - prev_vix_close) / prev_vix_close
                 if pct_change >= 0.20:
                     logger.critical(f"VIX CIRCUIT BREAKER TRIPPED! VIX spiked {pct_change*100:.1f}%")
                     return True
        return False

    @staticmethod
    def get_macro_trend_veto(macro_data: Dict[str, pd.DataFrame]) -> str:
        """Determines Risk-On/Risk-Off regime based on DXY and TNX."""
        # Simplified: If DXY and TNX are both rising strongly, it's Risk-Off (Bad for Metals/Emerging FX)
        dxy_ticker, tnx_ticker = "DX-Y.NYB", "^TNX"
        if dxy_ticker in macro_data and tnx_ticker in macro_data:
             dxy = macro_data[dxy_ticker]
             tnx = macro_data[tnx_ticker]

             if len(dxy) > 5 and len(tnx) > 5:
                  dxy_trend = dxy['close'].iloc[-1] > dxy['close'].iloc[-5]
                  tnx_trend = tnx['close'].iloc[-1] > tnx['close'].iloc[-5]

                  if dxy_trend and tnx_trend:
                      return "RISK_OFF" # Strong USD & Yields -> Veto Long Metals
                  elif not dxy_trend and not tnx_trend:
                      return "RISK_ON" # Weak USD & Yields -> Favor Long Metals
        return "NEUTRAL"


class SentimentFilter:
    """Uses NLTK VADER to analyze RSS news feeds to generate sentiment vetoes."""

    # Cache to avoid parsing feeds every minute
    _sentiment_cache = {}
    _last_update = datetime.min

    @classmethod
    def update_sentiment(cls):
        """Fetches RSS feeds and updates the cache."""
        now = datetime.utcnow()
        if now - cls._last_update < timedelta(hours=1):
             return # Only update hourly

        logger.info("Updating News Sentiment Cache via RSS...")
        analyzer = SentimentIntensityAnalyzer()

        # Example RSS feeds (Free)
        feeds = [
            "https://finance.yahoo.com/news/rssindex",
            # Add other free financial RSS feeds here
        ]

        # Aggregate text
        texts = []
        for url in feeds:
            try:
                 parsed = feedparser.parse(url)
                 for entry in parsed.entries[:10]: # Top 10 from each
                     texts.append(entry.title + ". " + getattr(entry, 'summary', ''))
            except Exception as e:
                 logger.error(f"Failed to parse RSS feed {url}: {e}")

        if not texts:
            return

        # Analyze overall macro sentiment
        compound_scores = []
        for text in texts:
            score = analyzer.polarity_scores(text)['compound']
            compound_scores.append(score)

        avg_score = sum(compound_scores) / len(compound_scores)
        cls._sentiment_cache['macro'] = avg_score
        cls._last_update = now

        logger.info(f"Updated Macro Sentiment Score: {avg_score:.2f}")

    @classmethod
    def check_sentiment_veto(cls, ticker: str, direction: str) -> bool:
        """Returns True if sentiment strongly disagrees with technical direction."""
        if 'macro' not in cls._sentiment_cache:
            cls.update_sentiment()

        score = cls._sentiment_cache.get('macro', 0.0)

        # Strong negative sentiment (-0.5) vetoes Longs in risk assets (Metals)
        asset_class = get_asset_class(ticker)

        if asset_class == "Metals":
             if direction == "Long" and score <= -0.50:
                  logger.warning(f"SENTIMENT VETO: Rejecting {direction} on {ticker}. Score: {score:.2f}")
                  return True
             if direction == "Short" and score >= 0.50:
                  logger.warning(f"SENTIMENT VETO: Rejecting {direction} on {ticker}. Score: {score:.2f}")
                  return True

        return False
