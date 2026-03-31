import yfinance as yf
import pandas as pd
import asyncio
from typing import Dict, Optional
from src.logger import logger

class DataLoader:
    def __init__(self, tickers: list):
        self.tickers = tickers

    async def fetch_historical_data(self, ticker: str, interval: str = "1h", period: str = "1y", retries: int = 3) -> Optional[pd.DataFrame]:
        for attempt in range(retries):
            try:
                # Use asyncio.to_thread for blocking calls
                df = await asyncio.to_thread(yf.download, tickers=ticker, interval=interval, period=period, progress=False)

                if df.empty:
                    logger.warning(f"No data returned for {ticker}. Attempt {attempt+1}/{retries}")
                    await asyncio.sleep(2 ** attempt)
                    continue

                # Forward fill NaNs for missing days/holidays
                df = df.ffill().bfill()
                df.index = pd.to_datetime(df.index).tz_localize(None) # Strip timezone for merging

                return df

            except Exception as e:
                logger.error(f"Error fetching data for {ticker}: {e}. Attempt {attempt+1}/{retries}")
                await asyncio.sleep(2 ** attempt)

        return None

    async def get_all_data(self, interval: str = "1h", period: str = "1y") -> Dict[str, pd.DataFrame]:
        tasks = [self.fetch_historical_data(t, interval, period) for t in self.tickers]
        results = await asyncio.gather(*tasks)
        return {ticker: df for ticker, df in zip(self.tickers, results) if df is not None}

if __name__ == "__main__":
    async def test():
        dl = DataLoader(["GC=F", "USDTRY=X"])
        data = await dl.get_all_data(interval="1d", period="1mo")
        for t, df in data.items():
            print(f"{t}:\n{df.tail()}")
    asyncio.run(test())
