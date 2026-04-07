import yfinance as yf
import pandas as pd
import asyncio
from typing import Dict, Tuple
from .logger import quant_logger
from .config import TICKERS

class DataLoader:
    def __init__(self):
        self.tickers = list(TICKERS.keys())

    async def _fetch_single(self, ticker: str, interval: str, period: str) -> pd.DataFrame:
        try:
            # yfinance is blocking, run in thread
            df = await asyncio.to_thread(yf.download, tickers=ticker, interval=interval, period=period, progress=False)
            if df.empty:
                return pd.DataFrame()

            # Flatten multi-index columns if yfinance returns them
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df.dropna(inplace=True)
            return df
        except Exception as e:
            quant_logger.error(f"Failed fetching {ticker} ({interval}): {e}")
            return pd.DataFrame()

    async def get_mtf_data(self, ticker: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch Daily (HTF) and Hourly (LTF) data asynchronously.
        """
        # Fetch HTF (1d) and LTF (1h) concurrently
        task_htf = self._fetch_single(ticker, interval="1d", period="2y")
        task_ltf = self._fetch_single(ticker, interval="1h", period="1y")

        df_htf, df_ltf = await asyncio.gather(task_htf, task_ltf)

        # Ensure timezone stripping to avoid merge_asof errors
        for df in [df_htf, df_ltf]:
            if not df.empty and df.index.tz is not None:
                df.index = df.index.tz_localize(None)

        return df_htf, df_ltf

    async def fetch_all(self) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        """Fetch MTF data for all tickers."""
        quant_logger.info("Starting MTF data fetch for entire universe...")
        tasks = {t: self.get_mtf_data(t) for t in self.tickers}
        results = {}
        for ticker, task in tasks.items():
            results[ticker] = await task
        quant_logger.info("MTF data fetch complete.")
        return results
