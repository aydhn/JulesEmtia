import yfinance as yf
import pandas as pd
import asyncio
from typing import Dict, Optional, Tuple
from core.logger import setup_logger
from core.config import UNIVERSE
import time

logger = setup_logger("data_engine")

class DataEngine:
    """
    Asynchronous data ingestion engine handling rate limits, forward filling,
    and multi-timeframe OHLCV fetching via yfinance.
    """
    def __init__(self):
        self.universe = list(UNIVERSE.keys())
        self.max_retries = 3

    async def _fetch_single_ticker(self, ticker: str, interval: str, period: str) -> Optional[pd.DataFrame]:
        for attempt in range(self.max_retries):
            try:
                # Async wrapper around blocking yf call
                df = await asyncio.to_thread(
                    yf.download,
                    tickers=ticker,
                    period=period,
                    interval=interval,
                    progress=False,
                    auto_adjust=False # Ensure raw OHLCV
                )

                if df.empty:
                    logger.warning(f"[{ticker}] Returned empty DataFrame for interval {interval}")
                    return None

                # yfinance >= 0.2.31 multi-index fix
                if isinstance(df.columns, pd.MultiIndex):
                    # For a single ticker, level 0 is the OHLCV strings, level 1 is the ticker
                    if len(df.columns.levels) > 1 and df.columns.levels[1].str.contains(ticker).any():
                        df.columns = df.columns.droplevel(1)

                df.columns = [col.lower() for col in df.columns]

                # Drop dividends and stock splits if they exist
                cols_to_drop = [c for c in df.columns if c in ['dividends', 'stock splits']]
                if cols_to_drop:
                    df.drop(columns=cols_to_drop, inplace=True)

                # Quant Cleaning: Handle NaNs and forward fill
                df.ffill(inplace=True)
                df.dropna(inplace=True) # Drop initial NaNs if any

                return df

            except Exception as e:
                wait_time = 2 ** attempt
                logger.error(f"[{ticker}] Fetch error on attempt {attempt+1}: {e}. Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        logger.critical(f"[{ticker}] Failed to fetch data after {self.max_retries} attempts.")
        return None

    async def fetch_mtf_data(self) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Fetches Higher Timeframe (HTF: 1d) and Lower Timeframe (LTF: 1h)
        Returns a dictionary mapping ticker to a tuple of (htf_df, ltf_df).
        """
        logger.info("Starting Multi-Timeframe (MTF) Data Fetching...")
        results = {}

        # We will fetch sequentially with small delays to respect rate limits,
        # but you can use asyncio.gather for parallel fetching if safe.
        # To be safe with yfinance rate limits, we use a controlled async loop.

        for ticker in self.universe:
            # HTF: 1 year of daily data
            htf_df = await self._fetch_single_ticker(ticker, interval="1d", period="1y")
            await asyncio.sleep(0.5) # Rate limit protection

            # LTF: 60 days of hourly data (yfinance limit for 1h is 730d max)
            ltf_df = await self._fetch_single_ticker(ticker, interval="1h", period="60d")
            await asyncio.sleep(0.5) # Rate limit protection

            if htf_df is not None and not htf_df.empty and ltf_df is not None and not ltf_df.empty:
                results[ticker] = (htf_df, ltf_df)
            else:
                logger.warning(f"[{ticker}] Insufficient MTF data. Skipping.")

        logger.info(f"Successfully fetched MTF data for {len(results)}/{len(self.universe)} tickers.")
        return results
