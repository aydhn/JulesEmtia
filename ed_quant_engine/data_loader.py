import yfinance as yf
import pandas as pd
import time
from typing import Dict, List, Optional
from ed_quant_engine.logger import log
from ed_quant_engine.config import UNIVERSE

def fetch_data(ticker: str, timeframe: str = '1d', retries: int = 3, backoff: int = 5) -> Optional[pd.DataFrame]:
    """Fetches historical OHLCV data from yfinance with exponential backoff."""
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period="1y", interval=timeframe, progress=False)
            if df.empty:
                log.warning(f"No data fetched for {ticker} on {timeframe}. Attempt {attempt+1}/{retries}")
                continue

            # Flatten MultiIndex columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Ensure required columns exist
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required_cols):
                log.warning(f"Missing required columns for {ticker}. Found: {df.columns.tolist()}")
                return None

            df = df[required_cols]

            # Forward-fill to handle NaNs from holidays/weekends
            df.ffill(inplace=True)

            # Drop any remaining NaNs at the beginning
            df.dropna(inplace=True)

            log.info(f"Successfully fetched {len(df)} rows for {ticker} ({timeframe})")
            return df

        except Exception as e:
            log.error(f"Error fetching {ticker} on {timeframe} (Attempt {attempt+1}/{retries}): {e}")

        time.sleep(backoff * (2 ** attempt)) # Exponential backoff: 5, 10, 20

    log.error(f"Failed to fetch data for {ticker} after {retries} retries.")
    return None

def fetch_universe_data(universe: Dict[str, List[str]], timeframes: List[str] = ['1d', '1h']) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Fetches MTF data for the entire universe."""
    all_data = {}
    total_tickers = sum(len(tickers) for tickers in universe.values())
    processed = 0

    for category, tickers in universe.items():
        for ticker in tickers:
            ticker_data = {}
            for tf in timeframes:
                df = fetch_data(ticker, tf)
                if df is not None:
                    ticker_data[tf] = df

            if ticker_data:
                all_data[ticker] = ticker_data

            processed += 1
            if processed % 5 == 0:
                time.sleep(2) # Prevent rate-limiting

    log.info(f"Finished fetching data for {len(all_data)}/{total_tickers} tickers.")
    return all_data

if __name__ == "__main__":
    test_universe = {"metals": ["GC=F"]}
    data = fetch_universe_data(test_universe)
    if "GC=F" in data:
        print(data["GC=F"]["1d"].tail())
