import yfinance as yf
import pandas as pd
import asyncio
import logging

logger = logging.getLogger(__name__)

class DataEngine:
    """
    Phase 2: Data Loading
    Phase 16: Async MTF Loading
    """
    def __init__(self, ticker_dict: dict):
        self.tickers = ticker_dict
        self.all_tickers = [ticker for group in self.tickers.values() for ticker in group]

    async def fetch_mtf_data(self, ticker: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetches 1D and 1H data asynchronously."""
        try:
            # yfinance operations are blocking, run in thread
            htf = await asyncio.to_thread(
                yf.download, tickers=ticker, period="2y", interval="1d", progress=False
            )
            ltf = await asyncio.to_thread(
                yf.download, tickers=ticker, period="60d", interval="1h", progress=False
            )

            # Basic cleaning (Phase 2)
            if not htf.empty: htf.ffill(inplace=True)
            if not ltf.empty: ltf.ffill(inplace=True)

            # Flatten MultiIndex columns if present (yfinance v0.2.x+ behavior)
            if isinstance(htf.columns, pd.MultiIndex):
                htf.columns = [col[0] for col in htf.columns]
            if isinstance(ltf.columns, pd.MultiIndex):
                ltf.columns = [col[0] for col in ltf.columns]

            return htf, ltf
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame(), pd.DataFrame()
