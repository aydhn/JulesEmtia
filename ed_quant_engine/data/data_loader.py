import yfinance as yf
import pandas as pd
import asyncio
import time
from typing import Dict
from ed_quant_engine.utils.logger import setup_logger

logger = setup_logger("DataLoader")

class DataLoader:
    def __init__(self, tickers: list):
        self.tickers = tickers

    async def fetch_historical_data_async(self, period="2y", htf="1d", ltf="1h") -> Dict[str, Dict[str, pd.DataFrame]]:
        """Asynchronously fetches HTF and LTF data for the universe."""
        data = {}
        for ticker in self.tickers:
            try:
                htf_df = yf.download(ticker, period=period, interval=htf, progress=False, group_by="ticker")
                await asyncio.sleep(0.5) # Rate limit protection
                ltf_df = yf.download(ticker, period="730d", interval=ltf, progress=False, group_by="ticker")
                await asyncio.sleep(0.5)

                if not htf_df.empty and not ltf_df.empty:
                    # Clean multi-index if exists
                    if isinstance(htf_df.columns, pd.MultiIndex):
                         htf_df.columns = htf_df.columns.droplevel(0)
                    if isinstance(ltf_df.columns, pd.MultiIndex):
                         ltf_df.columns = ltf_df.columns.droplevel(0)

                    # Handle NaNs and missing values professionally
                    htf_df.ffill(inplace=True)
                    ltf_df.ffill(inplace=True)

                    data[ticker] = {"HTF": htf_df, "LTF": ltf_df}
                    logger.info(f"Successfully loaded {ticker} (HTF: {len(htf_df)}, LTF: {len(ltf_df)})")
                else:
                    logger.warning(f"Empty DataFrame for {ticker}")

            except Exception as e:
                logger.error(f"Error fetching data for {ticker}: {e}")
                # Exponential backoff placeholder logic could go here

        return data
