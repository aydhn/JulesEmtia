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

    async def fetch_mtf_data(self, ticker: str, period_1d="2y", period_1h="60d") -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetches 1D and 1H data asynchronously."""
        try:
            # yfinance operations are blocking, run in thread
            htf = await asyncio.to_thread(
                yf.download, tickers=ticker, period=period_1d, interval="1d", progress=False
            )
            ltf = await asyncio.to_thread(
                yf.download, tickers=ticker, period=period_1h, interval="1h", progress=False
            )

            # Basic cleaning (Phase 2)
            if not htf.empty: htf.ffill(inplace=True)
            if not ltf.empty: ltf.ffill(inplace=True)

            # Flatten MultiIndex columns if present (yfinance v0.2.x+ behavior)
            if isinstance(htf.columns, pd.MultiIndex):
                htf.columns = [col[0] for col in htf.columns]
            if isinstance(ltf.columns, pd.MultiIndex):
                ltf.columns = [col[0] for col in ltf.columns]

            # Drop missing values
            htf.dropna(inplace=True)
            ltf.dropna(inplace=True)

            return htf, ltf
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame(), pd.DataFrame()

    def merge_mtf_data(self, htf: pd.DataFrame, ltf: pd.DataFrame) -> pd.DataFrame:
        """
        Merge HTF (Daily) and LTF (Hourly) data cleanly.
        Phase 16: STRICT LOOKAHEAD BIAS PROTECTION.
        """
        if htf.empty or ltf.empty:
            return ltf

        # Strip timezone information from both dataframes to avoid merge errors
        if htf.index.tzinfo is not None:
            htf.index = htf.index.tz_localize(None)
        if ltf.index.tzinfo is not None:
            ltf.index = ltf.index.tz_localize(None)

        # 1) Shift HTF by 1 so today's daily close is only available TOMORROW.
        htf_shifted = htf.shift(1).copy()

        # Rename columns to avoid collision
        htf_shifted.columns = [f"{c}_HTF" for c in htf_shifted.columns]

        # Ensure indices are named for merge_asof
        htf_shifted.index.name = "Date"
        ltf.index.name = "Date"

        # Sort indices required by merge_asof
        htf_shifted.sort_index(inplace=True)
        ltf.sort_index(inplace=True)

        # 2) Merge using merge_asof backward
        # For an hourly row at "2024-01-02 14:00:00", it matches the most recent HTF row (which is shifted, so it represents 2024-01-01's closed candle)
        merged_df = pd.merge_asof(
            ltf,
            htf_shifted,
            left_index=True,
            right_index=True,
            direction="backward"
        )

        merged_df.dropna(inplace=True)
        return merged_df
