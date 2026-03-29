import yfinance as yf
import pandas as pd
import numpy as np
import time
from typing import Dict, Optional, Tuple
from ed_quant_engine.core.logger import logger

def fetch_data(ticker: str, period: str = "2y", interval: str = "1d", max_retries: int = 3) -> pd.DataFrame:
    """
    Fetches OHLCV data from yfinance with Exponential Backoff.
    """
    for attempt in range(max_retries):
        try:
            # Download data silently
            df = yf.download(tickers=ticker, period=period, interval=interval, progress=False)

            if df.empty:
                logger.warning(f"No data returned for {ticker} (Attempt {attempt+1}/{max_retries})")
                time.sleep(2 ** attempt)
                continue

            # Clean MultiIndex columns if present (yfinance specific issue)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Drop timezone information to avoid tz-naive/tz-aware mixing issues later
            if df.index.tz is not None:
                df.index = df.index.tz_convert(None)

            # Handle missing data professionally
            df.ffill(inplace=True)
            df.bfill(inplace=True)

            return df

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e} (Attempt {attempt+1}/{max_retries})")
            time.sleep((2 ** attempt) * 2) # Exponential backoff 2, 4, 8 seconds

    logger.critical(f"Failed to fetch data for {ticker} after {max_retries} attempts.")
    return pd.DataFrame()

def fetch_multi_timeframe(ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetches HTF (1d) and LTF (1h) data.
    """
    htf = fetch_data(ticker, period="5y", interval="1d")
    # yfinance only allows 1h data for the last 730 days max
    ltf = fetch_data(ticker, period="730d", interval="1h")
    return htf, ltf

if __name__ == "__main__":
    df = fetch_data("GC=F", "1mo", "1d")
    print(df.tail())
