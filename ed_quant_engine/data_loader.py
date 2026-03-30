import yfinance as yf
import pandas as pd
import numpy as np
import asyncio
from typing import Dict, Tuple, Optional
from datetime import datetime

from logger import log

# Define the complete trading universe (Commodities and TRY-based Forex).
# Added majors (Heating Oil = HO=F, Gasoline = RB=F) and CHF/AUD.
UNIVERSE = {
    # Precious Metals
    "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    "Palladium": "PA=F", "Platinum": "PL=F",
    # Energy
    "WTI": "CL=F", "Brent": "BZ=F", "NatGas": "NG=F",
    "HeatingOil": "HO=F", "Gasoline": "RB=F",
    # Agriculture
    "Wheat": "ZW=F", "Corn": "ZC=F", "Soybean": "ZS=F",
    "Coffee": "KC=F", "Cocoa": "CC=F", "Sugar": "SB=F", "Cotton": "CT=F",
    # Forex (TRY)
    "USD/TRY": "USDTRY=X", "EUR/TRY": "EURTRY=X", "GBP/TRY": "GBPTRY=X",
    "JPY/TRY": "JPYTRY=X", "CNH/TRY": "CNHY=X", "CHF/TRY": "CHFTRY=X", "AUD/TRY": "AUDTRY=X"
}


def _download_yf_data(ticker: str, timeframe: str, period: str) -> pd.DataFrame:
    """Synchronous internal method to fetch and clean yfinance data with forward-fill."""
    try:
        # Download historical data from Yahoo Finance API.
        df = yf.download(ticker, period=period, interval=timeframe, auto_adjust=False, progress=False)

        # In case of no data
        if df.empty:
            log.warning(f"No data returned for {ticker} at {timeframe}")
            return pd.DataFrame()

        # Handle Pandas MultiIndex columns (yf.download recent changes)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # Standardize column names
        df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)

        # Professional Forward Fill to handle NaN gaps from weekends/holidays
        df = df[['open', 'high', 'low', 'close', 'volume']].ffill()

        # Drop any remaining NaNs at the very beginning of the dataset
        df.dropna(inplace=True)

        return df

    except Exception as e:
        log.error(f"Error fetching data for {ticker} ({timeframe}): {e}")
        return pd.DataFrame()


async def fetch_mtf_data(ticker: str, htf_period: str = "2y", ltf_period: str = "60d") -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Asynchronously fetches Multi-Timeframe (MTF) Data using asyncio.to_thread
    to avoid blocking the main event loop.
    Returns: Tuple of (HTF DataFrame '1d', LTF DataFrame '1h')
    """
    try:
        # Run yfinance blocking calls in separate threads to avoid blocking asyncio loop
        htf_df_task = asyncio.to_thread(_download_yf_data, ticker, "1d", htf_period)
        ltf_df_task = asyncio.to_thread(_download_yf_data, ticker, "1h", ltf_period)

        htf_df, ltf_df = await asyncio.gather(htf_df_task, ltf_df_task)

        if htf_df.empty or ltf_df.empty:
            log.warning(f"Empty MTF data retrieved for {ticker}.")
            return None, None

        # Clean timezones to prevent merge_asof issues
        htf_df.index = htf_df.index.tz_localize(None)
        ltf_df.index = ltf_df.index.tz_localize(None)

        return htf_df, ltf_df

    except Exception as e:
        log.error(f"Async MTF Data Fetch Failed for {ticker}: {e}")
        return None, None


def align_mtf_data(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aligns Daily (HTF) data onto Hourly (LTF) data with strict lookahead bias prevention.
    The Daily data must be shifted by 1 BEFORE merging so that the 1H candle only sees
    the completed daily data of yesterday.
    """
    if htf_df is None or ltf_df is None or htf_df.empty or ltf_df.empty:
        return pd.DataFrame()

    # Create explicit copy and append '_htf' suffix to prevent column overlap
    htf_copy = htf_df.copy()
    htf_copy.columns = [f"{col}_htf" for col in htf_copy.columns]

    # STRCIT LOOKAHEAD BIAS PREVENTION
    # Shift HTF data forward by 1 day. This guarantees that at any point today,
    # the HTF feature values only reflect yesterday's closed daily candle.
    htf_shifted = htf_copy.shift(1).dropna()

    # Merge asof (backward) ensures that each 1H timestamp gets the most recent valid HTF value.
    merged_df = pd.merge_asof(
        ltf_df.sort_index(),
        htf_shifted.sort_index(),
        left_index=True,
        right_index=True,
        direction="backward"
    )

    return merged_df.dropna()
