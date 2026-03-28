import yfinance as yf
import pandas as pd
import time
from typing import Dict, Tuple
from config import HTF, LTF
from logger import get_logger

log = get_logger()

# Exponential Backoff Decorator (Self-Healing)
def retry_with_backoff(max_retries=3, initial_wait=60):
    def decorator(func):
        def wrapper(*args, **kwargs):
            retries = 0
            wait_time = initial_wait
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    log.warning(f"Error in {func.__name__}: {str(e)}. Retrying {retries+1}/{max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                    retries += 1
                    wait_time *= 2
            log.error(f"Max retries reached for {func.__name__}. Failing gracefully.")
            return None
        return wrapper
    return decorator

@retry_with_backoff(max_retries=3, initial_wait=60)
def fetch_mtf_data(ticker: str, period_htf="2y", period_ltf="1mo") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetches Daily (HTF) and Hourly (LTF) data, avoiding lookahead bias by shifting HTF."""
    htf = yf.download(ticker, period=period_htf, interval=HTF, progress=False)
    if htf.empty:
        raise ValueError(f"Empty HTF data for {ticker}")

    ltf = yf.download(ticker, period=period_ltf, interval=LTF, progress=False)
    if ltf.empty:
        raise ValueError(f"Empty LTF data for {ticker}")

    # Forward fill missing data, drop entirely NaN columns
    htf = htf.ffill().dropna()
    ltf = ltf.ffill().dropna()

    log.info(f"Fetched MTF data for {ticker}. HTF: {len(htf)}, LTF: {len(ltf)}")
    return htf, ltf

def merge_mtf(htf: pd.DataFrame, ltf: pd.DataFrame) -> pd.DataFrame:
    """Merges Daily signals into Hourly data with absolute strictness to prevent Lookahead Bias."""
    # Ensure indices are timezone-aware and matched.
    if htf.index.tz is None:
        htf.index = htf.index.tz_localize('UTC')
    else:
        htf.index = htf.index.tz_convert('UTC')

    if ltf.index.tz is None:
        ltf.index = ltf.index.tz_localize('UTC')
    else:
        ltf.index = ltf.index.tz_convert('UTC')

    # VERY IMPORTANT: Shift HTF data by 1 period (1 day) BEFORE merging to prevent
    # the current day's close from leaking into the current day's hourly candles.
    htf_shifted = htf.shift(1).copy()
    htf_shifted.index = htf_shifted.index.normalize() # Ensure daily precision

    # Add _HTF suffix to avoid column clash
    htf_shifted.columns = [f"{c}_HTF" for c in htf_shifted.columns]

    # Forward merge daily into hourly (asof merge to find the most recent *closed* daily candle)
    # Using merge_asof is safer than reindexing
    merged = pd.merge_asof(ltf.sort_index(), htf_shifted.sort_index(), left_index=True, right_index=True, direction='backward')
    return merged.dropna()
