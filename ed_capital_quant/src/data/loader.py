import yfinance as yf
import pandas as pd
from src.core.logger import logger
import asyncio
from typing import Dict, Optional
import gc

class DataLoader:
    def __init__(self, tickers: list[str]):
        self.tickers = tickers
        self._cache = {}

    def fetch_data(self, ticker: str, interval: str = "1h", period: str = "60d") -> Optional[pd.DataFrame]:
        try:
            df = yf.download(ticker, interval=interval, period=period, progress=False)
            if df.empty:
                logger.warning(f"No data returned for {ticker} at {interval}")
                return None
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            df.index = pd.to_datetime(df.index)
            # Handle NaN and forward fill
            df.ffill(inplace=True)
            df.dropna(inplace=True)
            logger.debug(f"Fetched {len(df)} rows for {ticker} ({interval})")
            return df
        except Exception as e:
            logger.error(f"Error fetching {ticker} ({interval}): {e}")
            return None

    async def fetch_mtf_data(self, ticker: str) -> Dict[str, pd.DataFrame]:
        logger.info(f"Fetching MTF data for {ticker}...")
        loop = asyncio.get_event_loop()
        # Fetch HTF (Daily) and LTF (Hourly) concurrently
        htf_task = loop.run_in_executor(None, self.fetch_data, ticker, "1d", "2y")
        ltf_task = loop.run_in_executor(None, self.fetch_data, ticker, "1h", "60d")

        htf_df, ltf_df = await asyncio.gather(htf_task, ltf_task)

        if htf_df is None or ltf_df is None:
            return {}

        # Clean memory periodically
        gc.collect()

        return {"HTF": htf_df, "LTF": ltf_df}

    def align_mtf_data(self, htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merges daily data into hourly data strictly preventing lookahead bias.
        Daily data is shifted by 1 so hourly bars only see fully closed previous daily bars.
        """
        htf_shifted = htf_df.shift(1).copy()
        htf_shifted.columns = [f"HTF_{col}" for col in htf_shifted.columns]

        ltf_df = ltf_df.copy()
        ltf_df['date_only'] = ltf_df.index.normalize()
        htf_shifted['date_only'] = htf_shifted.index.normalize()

        merged_df = pd.merge_asof(
            ltf_df.sort_index(),
            htf_shifted.sort_index(),
            left_on='date_only',
            right_on='date_only',
            direction='backward'
        )
        merged_df.index = ltf_df.index
        merged_df.drop(columns=['date_only'], inplace=True)
        return merged_df

if __name__ == "__main__":
    import asyncio
    loader = DataLoader(["GC=F"])
    async def test():
        data = await loader.fetch_mtf_data("GC=F")
        if data:
            aligned = loader.align_mtf_data(data["HTF"], data["LTF"])
            print(aligned.tail())
    asyncio.run(test())
