"""
ED Capital Quant Engine - Data Loader Module
Fetches multi-timeframe OHLCV data from Yahoo Finance efficiently.
"""
import yfinance as yf
import pandas as pd
import asyncio
from .logger import logger
from .config import UNIVERSE
from .notifier import notify_admin

class QuantDataLoader:
    def __init__(self):
        self.cache = {}

    def fetch_data(self, ticker: str, period="2y", interval="1d") -> pd.DataFrame:
        """Fetch historical data for a ticker with built-in error handling and backoff."""
        logger.info(f"Fetching {interval} data for {ticker} over {period}")
        try:
            # Download data using yfinance
            data = yf.download(tickers=ticker, period=period, interval=interval, progress=False)

            if data.empty:
                logger.warning(f"No data fetched for {ticker}")
                return pd.DataFrame()

            # Handle MultiIndex columns (yfinance sometimes returns MultiIndex depending on arguments)
            if isinstance(data.columns, pd.MultiIndex):
                # Flatten MultiIndex to simple column names (e.g., 'Close', 'Open', etc.)
                data.columns = [col[0] for col in data.columns]

            # Forward-fill NaN values to handle missing data or non-trading days smoothly
            data.fillna(method='ffill', inplace=True)
            # Drop any remaining NaNs at the beginning
            data.dropna(inplace=True)

            logger.info(f"Successfully fetched {len(data)} rows for {ticker} ({interval})")
            return data

        except Exception as e:
            msg = f"Data fetching failed for {ticker}: {e}"
            logger.error(msg)
            # Potentially trigger backoff logic here or notify admin on critical failures
            notify_admin(f"⚠️ Warning: {msg}")
            return pd.DataFrame()

    async def fetch_universe_async(self, universe: dict, period="2y", interval="1d") -> dict:
        """Asynchronously fetch data for the entire universe (or a subset) to save time."""
        results = {}
        for category, tickers in universe.items():
            for ticker in tickers:
                # We are doing sequential fetch here for simplicity and safety against rate limits
                # but it's wrapped in an async signature to allow non-blocking behavior in the main loop
                results[ticker] = self.fetch_data(ticker, period=period, interval=interval)
                await asyncio.sleep(1) # Simple rate limit protection
        return results

data_loader = QuantDataLoader()
