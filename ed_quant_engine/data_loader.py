import yfinance as yf
import pandas as pd
import numpy as np
import time
from typing import Dict, Optional
from config import ALL_TICKERS, HTF, LTF
from logger import log

class DataLoader:
    def __init__(self, tickers=ALL_TICKERS):
        self.tickers = tickers

    def _fetch_data_with_retry(self, ticker: str, interval: str, period: str, max_retries: int = 3) -> pd.DataFrame:
        """Fetches data from yfinance with exponential backoff for rate limits."""
        for attempt in range(max_retries):
            try:
                log.info(f"Fetching {ticker} [{interval}] (Attempt {attempt+1}/{max_retries})")
                df = yf.download(ticker, period=period, interval=interval, progress=False)

                # Handle multi-level columns if returned by newer yfinance versions
                if isinstance(df.columns, pd.MultiIndex):
                    # For a single ticker, drop the ticker level
                    df.columns = df.columns.droplevel(1)

                if df.empty:
                    log.warning(f"Empty dataframe returned for {ticker}")
                    # If empty, might be weekend/holiday, not necessarily an error, but we retry just in case
                    time.sleep(2 ** attempt)
                    continue

                # Clean up NaN values via forward fill (common in forex/commodities)
                df.ffill(inplace=True)
                df.dropna(inplace=True) # Drop initial NaNs

                # Strip timezone for MTF alignment safety
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)

                return df

            except Exception as e:
                log.error(f"Error fetching {ticker}: {e}")
                if attempt < max_retries - 1:
                    sleep_time = (2 ** attempt) * 60 # 1m, 2m, 4m
                    log.info(f"Sleeping for {sleep_time}s before retry...")
                    time.sleep(sleep_time)
                else:
                    log.error(f"Max retries reached for {ticker}")
                    return pd.DataFrame()
        return pd.DataFrame()

    def get_mtf_data(self, ticker: str, period_htf: str = "2y", period_ltf: str = "60d") -> Dict[str, pd.DataFrame]:
        """Fetches both Higher Timeframe (1d) and Lower Timeframe (1h) data."""
        df_htf = self._fetch_data_with_retry(ticker, HTF, period_htf)
        df_ltf = self._fetch_data_with_retry(ticker, LTF, period_ltf)

        return {"HTF": df_htf, "LTF": df_ltf}

    def fetch_all_current_data(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Scans universe and returns dictionary of HTF/LTF dataframes."""
        data_dict = {}
        for ticker in self.tickers:
            data = self.get_mtf_data(ticker)
            if not data["HTF"].empty and not data["LTF"].empty:
                data_dict[ticker] = data
            time.sleep(1) # Polite delay
        return data_dict
