from __future__ import annotations

import pandas as pd

from src.data_loader import fetch_ticker_data_async
from src.features import merge_mtf_data


class DataEngine:
    """Backward-compatible facade over the canonical data_loader/features path."""

    def __init__(self, ticker_dict: dict):
        self.tickers = ticker_dict
        self.all_tickers = [ticker for group in self.tickers.values() for ticker in group]

    async def fetch_mtf_data(
        self,
        ticker: str,
        period_1d: str = "2y",
        period_1h: str = "60d",
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        htf = await fetch_ticker_data_async(ticker, period=period_1d, interval="1d")
        ltf = await fetch_ticker_data_async(ticker, period=period_1h, interval="1h")
        return htf, ltf

    def merge_mtf_data(self, htf: pd.DataFrame, ltf: pd.DataFrame) -> pd.DataFrame:
        return merge_mtf_data(ltf, htf)
