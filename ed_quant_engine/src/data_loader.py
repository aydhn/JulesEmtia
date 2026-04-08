import yfinance as yf
import pandas as pd
import numpy as np
import asyncio
from src.logger import get_logger

logger = get_logger()

async def fetch_ticker_data_async(ticker: str, period: str = "2y", interval: str = "1h") -> pd.DataFrame:
    """
    Fetches OHLCV data using yfinance asynchronously to avoid blocking the event loop.
    Applies forward fill and dropna to handle NaNs.
    """
    try:
        df = await asyncio.to_thread(yf.download, tickers=ticker, period=period, interval=interval, progress=False)
        if df.empty:
            logger.warning(f"No data returned for {ticker} at interval {interval}")
            return pd.DataFrame()

        # Flatten MultiIndex columns if yfinance returns them
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.ffill().dropna()
        if hasattr(df.index, 'tz_localize'):
            df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

async def get_mtf_data(ticker: str) -> dict:
    """
    Fetches both High Timeframe (1D) and Low Timeframe (1H) data.
    """
    ltf_task = fetch_ticker_data_async(ticker, period="730d", interval="1h")
    htf_task = fetch_ticker_data_async(ticker, period="5y", interval="1d")

    ltf_df, htf_df = await asyncio.gather(ltf_task, htf_task)
    return {"ltf": ltf_df, "htf": htf_df}

def fetch_macro_data() -> dict:
    """
    Fetches macro data (VIX, DXY, US10Y) synchronously for immediate use in filters.
    """
    try:
        tickers = ["^VIX", "DX-Y.NYB", "^TNX"]
        df = yf.download(tickers, period="5d", interval="1d", progress=False)
        if df.empty:
            return {}

        if isinstance(df.columns, pd.MultiIndex):
            df_close = df['Close']
        else:
            df_close = df

        df_close = df_close.ffill()

        vix = df_close["^VIX"].iloc[-1]
        dxy = df_close["DX-Y.NYB"].iloc[-1]
        us10y = df_close["^TNX"].iloc[-1]

        return {
            "VIX": float(vix.iloc[0]) if hasattr(vix, "iloc") else float(vix),
            "DXY": float(dxy.iloc[0]) if hasattr(dxy, "iloc") else float(dxy),
            "US10Y": float(us10y.iloc[0]) if hasattr(us10y, "iloc") else float(us10y)
        }
    except Exception as e:
        logger.error(f"Error fetching macro data: {e}")
        return {"VIX": 0.0, "DXY": 0.0, "US10Y": 0.0}
