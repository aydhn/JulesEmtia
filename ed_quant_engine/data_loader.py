import yfinance as yf
import pandas as pd
import asyncio
import gc
from typing import Dict, Optional, Tuple
from logger import logger

class DataLoader:
    """
    Data Ingestion Engine.
    Fetches Multi-Timeframe (MTF) OHLCV data from Yahoo Finance via yfinance.
    Follows Quant standards for NaN handling, Forward Filling, and Rate Limits.
    """

    TICKERS = {
        # Precious Metals
        "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
        "Palladium": "PA=F", "Platinum": "PL=F",

        # Energy
        "WTI Crude Oil": "CL=F", "Brent Crude Oil": "BZ=F",
        "Natural Gas": "NG=F", "Heating Oil": "HO=F", "Gasoline": "RB=F",

        # Agriculture & Softs
        "Wheat": "ZW=F", "Corn": "ZC=F", "Soybeans": "ZS=F",
        "Coffee": "KC=F", "Cocoa": "CC=F", "Sugar": "SB=F",
        "Cotton": "CT=F", "Live Cattle": "LE=F",

        # Forex (TRY-based Pairs)
        "USD/TRY": "USDTRY=X", "EUR/TRY": "EURTRY=X", "GBP/TRY": "GBPTRY=X",
        "JPY/TRY": "JPYTRY=X", "CNH/TRY": "CNHY=X", "CHF/TRY": "CHFTRY=X",
        "AUD/TRY": "AUDTRY=X"
    }

    @staticmethod
    def _fetch_sync(ticker: str, timeframe: str, period: str) -> Optional[pd.DataFrame]:
        """
        Synchronous fetch using yfinance.
        Handles retries, rate-limits, and NaN cleaning.
        """
        try:
            # yfinance returns tz-aware data for some pairs
            df = yf.download(tickers=ticker, interval=timeframe, period=period, progress=False, timeout=15)

            if df.empty:
                logger.warning(f"No data returned for {ticker} at {timeframe}")
                return None

            # Flatten multi-index columns if they exist
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Strip timezone to avoid merging conflicts (MTF)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Clean NaNs: Forward fill missing values due to holidays/weekends
            df.ffill(inplace=True)
            df.dropna(inplace=True)

            return df

        except Exception as e:
            logger.error(f"Error fetching data for {ticker} ({timeframe}): {e}")
            return None

    @classmethod
    async def fetch_mtf_data(cls, ticker: str, period: str = "1mo") -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Asynchronously fetches both Daily (1d) and Hourly (1h) data.
        MTF Pipeline: 1D for Trend, 1H for Entry.
        """
        logger.info(f"Fetching MTF data for {ticker}...")

        # Async tasks to prevent blocking main loop
        daily_task = asyncio.to_thread(cls._fetch_sync, ticker, "1d", period)
        hourly_task = asyncio.to_thread(cls._fetch_sync, ticker, "1h", period)

        daily_df, hourly_df = await asyncio.gather(daily_task, hourly_task)

        # Garbage collection hint for RAM efficiency
        gc.collect()

        return daily_df, hourly_df

    @classmethod
    async def get_all_universe_data(cls) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        """Fetches data for entire universe. Uses Exponential Backoff logic internally inside yfinance"""
        universe_data = {}
        for name, ticker in cls.TICKERS.items():
            daily, hourly = await cls.fetch_mtf_data(ticker, "2y")
            if daily is not None and hourly is not None:
                universe_data[name] = (daily, hourly)

            # Rate limit protection
            await asyncio.sleep(0.5)

        return universe_data

