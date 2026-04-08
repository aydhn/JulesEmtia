import yfinance as yf
import pandas as pd
import numpy as np
import asyncio
from src.logger import get_logger

logger = get_logger()

async def fetch_ticker_data_async(ticker: str, period: str = "2y", interval: str = "1h") -> pd.DataFrame:
    """
    Fetches OHLCV data using yfinance asynchronously with exponential backoff.
    Applies forward fill and dropna to handle NaNs.
    """
    for attempt in range(3):
        try:
            df = await asyncio.to_thread(yf.download, tickers=ticker, period=period, interval=interval, progress=False)
            if df.empty:
                logger.warning(f"No data returned for {ticker} at interval {interval} (Attempt {attempt+1})")
                sleep_time = 1 * (2 ** attempt)
                await asyncio.sleep(sleep_time)
                continue

            # Flatten MultiIndex columns if yfinance returns them
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.ffill().dropna()
            if hasattr(df.index, 'tz_localize'):
                df.index = df.index.tz_localize(None)
            return df
        except Exception as e:
            sleep_time = 1 * (2 ** attempt)
            logger.warning(f"Error fetching data for {ticker} (Attempt {attempt+1}): {e}. Retrying in {sleep_time}s...")
            await asyncio.sleep(sleep_time)

    logger.error(f"Failed to fetch data for {ticker} after 3 attempts.")
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
    Includes moving averages to determine Risk-On / Risk-Off regime.
    """
    try:
        tickers = ["^VIX", "DX-Y.NYB", "^TNX"]
        df = yf.download(tickers, period="2y", interval="1d", progress=False)
        if df.empty:
            return {}

        if isinstance(df.columns, pd.MultiIndex):
            df_close = df['Close']
        else:
            df_close = df

        df_close = df_close.ffill()

        vix = df_close["^VIX"].iloc[-1]

        # Calculate 50 EMAs
        dxy_ema_50 = df_close["DX-Y.NYB"].ewm(span=50, adjust=False).mean().iloc[-1]
        us10y_ema_50 = df_close["^TNX"].ewm(span=50, adjust=False).mean().iloc[-1]

        dxy = df_close["DX-Y.NYB"].iloc[-1]
        us10y = df_close["^TNX"].iloc[-1]

        vix_val = float(vix.iloc[0]) if hasattr(vix, "iloc") else float(vix)
        dxy_val = float(dxy.iloc[0]) if hasattr(dxy, "iloc") else float(dxy)
        us10y_val = float(us10y.iloc[0]) if hasattr(us10y, "iloc") else float(us10y)
        dxy_ema_val = float(dxy_ema_50.iloc[0]) if hasattr(dxy_ema_50, "iloc") else float(dxy_ema_50)
        us10y_ema_val = float(us10y_ema_50.iloc[0]) if hasattr(us10y_ema_50, "iloc") else float(us10y_ema_50)

        # Regime Calculation
        regime = "Risk-Off" if (dxy_val > dxy_ema_val) and (us10y_val > us10y_ema_val) else "Risk-On"

        return {
            "VIX": vix_val,
            "DXY": dxy_val,
            "US10Y": us10y_val,
            "DXY_EMA_50": dxy_ema_val,
            "US10Y_EMA_50": us10y_ema_val,
            "Regime": regime
        }
    except Exception as e:
        logger.error(f"Error fetching macro data: {e}")
        return {"VIX": 0.0, "DXY": 0.0, "US10Y": 0.0, "DXY_EMA_50": 0.0, "US10Y_EMA_50": 0.0, "Regime": "Risk-On"}
