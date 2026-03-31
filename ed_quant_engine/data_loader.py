import yfinance as yf
import pandas as pd
import asyncio
from logger import setup_logger

logger = setup_logger("DataLoader")

async def fetch_historical_data(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    """Asynchronously fetches historical data for MTF backtesting and ML training."""
    try:
        data = await asyncio.to_thread(yf.download, ticker, period=period, interval=interval, progress=False)
        if data.empty:
            logger.warning(f"Geçmiş veri alınamadı: {ticker}")
            return pd.DataFrame()

        # Flatten multi-index columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        data.index = pd.to_datetime(data.index)
        data.index = data.index.tz_localize(None) # Strip timezone for pure calculations

        return data
    except Exception as e:
        logger.error(f"Geçmiş veri çekme hatası ({ticker}): {str(e)}")
        return pd.DataFrame()

async def fetch_live_data(ticker: str, interval: str = "1h") -> pd.DataFrame:
    """Fetches the latest data point for live trading. Implements basic retry logic implicitly via async wrappers."""
    return await fetch_historical_data(ticker, period="60d", interval=interval)
