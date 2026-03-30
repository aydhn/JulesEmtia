import yfinance as yf
import pandas as pd
import numpy as np
import time
import asyncio
from typing import Dict, List, Optional
from src.logger import get_logger

logger = get_logger("data_loader")

# Master Trading Universe
UNIVERSE = {
    # Precious Metals
    "GC=F": "Gold", "SI=F": "Silver", "HG=F": "Copper", "PA=F": "Palladium", "PL=F": "Platinum",
    # Energy
    "CL=F": "Crude Oil WTI", "BZ=F": "Brent Oil", "NG=F": "Natural Gas", "RB=F": "Gasoline RBOB", "HO=F": "Heating Oil",
    # Agriculture / Softs
    "ZW=F": "Wheat", "ZC=F": "Corn", "ZS=F": "Soybeans", "KC=F": "Coffee", "CC=F": "Cocoa", "SB=F": "Sugar", "CT=F": "Cotton", "LE=F": "Live Cattle",
    # TRY based Forex
    "USDTRY=X": "USD/TRY", "EURTRY=X": "EUR/TRY", "GBPTRY=X": "GBP/TRY", "JPYTRY=X": "JPY/TRY", "CNHTRY=X": "CNH/TRY", "CHFTRY=X": "CHF/TRY", "AUDTRY=X": "AUD/TRY"
}

def fetch_ticker_data_sync(ticker: str, period: str = "2y", interval: str = "1d", retries: int = 3) -> pd.DataFrame:
    """Synchronous fetch with exponential backoff for a single ticker."""
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if df.empty:
                logger.warning(f"Empty dataframe returned for {ticker} ({interval}).")
                return pd.DataFrame()

            # Clean MultiIndex columns if returned by yfinance v0.2.x+
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Handle NaN / Missing values
            df = df.ffill().bfill()

            # Drop timezone information to avoid lookahead merge issues later
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            return df
        except Exception as e:
            wait_time = (2 ** attempt) * 2
            logger.error(f"Error fetching {ticker} ({interval}) attempt {attempt+1}/{retries}: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    logger.critical(f"Failed to fetch {ticker} data after {retries} attempts.")
    return pd.DataFrame()

async def fetch_universe_async(interval: str = "1d", period: str = "2y") -> Dict[str, pd.DataFrame]:
    """Asynchronously fetches data for the entire universe to optimize I/O and prevent rate limits."""
    results = {}

    async def fetch_task(ticker):
        # Using asyncio.to_thread to wrap synchronous yfinance calls
        try:
            # Stagger start slightly to avoid API rate limiting bursts
            await asyncio.sleep(np.random.uniform(0.1, 1.0))
            df = await asyncio.to_thread(fetch_ticker_data_sync, ticker, period, interval)
            if not df.empty:
                results[ticker] = df
        except Exception as e:
            logger.error(f"Async fetch failed for {ticker}: {e}")

    tasks = [fetch_task(ticker) for ticker in UNIVERSE.keys()]
    await asyncio.gather(*tasks)

    logger.info(f"Successfully fetched {len(results)}/{len(UNIVERSE)} assets for {interval} timeframe.")
    return results

def align_mtf_data(df_ltf: pd.DataFrame, df_htf: pd.DataFrame) -> pd.DataFrame:
    """Aligns High Timeframe (HTF) data to Low Timeframe (LTF) to prevent lookahead bias."""
    if df_htf.empty or df_ltf.empty:
        return df_ltf

    # Crucial Rule: Shift HTF by 1 before merging. We only know yesterday's close TODAY.
    df_htf_shifted = df_htf.shift(1).copy()

    # Suffix HTF columns to differentiate them
    df_htf_shifted.columns = [f"{col}_HTF" for col in df_htf_shifted.columns]

    # Merge As Of backwards to match closest HTF timestamps to LTF without looking ahead
    merged = pd.merge_asof(
        df_ltf.sort_index(),
        df_htf_shifted.sort_index(),
        left_index=True,
        right_index=True,
        direction='backward'
    )

    return merged
