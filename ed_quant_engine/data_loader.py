import yfinance as yf
import pandas as pd
from logger import logger
import asyncio

async def fetch_data_with_retry(ticker: str, period: str, interval: str, retries=3) -> pd.DataFrame:
    for attempt in range(retries):
        try:
            # Run blocking I/O in thread
            df = await asyncio.to_thread(yf.download, ticker, period=period, interval=interval, progress=False)
            if df.empty:
                raise ValueError(f"Empty dataframe returned for {ticker}")
            return df
        except Exception as e:
            logger.warning(f"Data fetch error for {ticker} (Attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to fetch {interval} data for {ticker} after {retries} attempts.")
                return pd.DataFrame()

async def fetch_mtf_data(ticker: str) -> pd.DataFrame:
    try:
        # Fetch data concurrently
        df_1d, df_1h = await asyncio.gather(
            fetch_data_with_retry(ticker, period="2y", interval="1d"),
            fetch_data_with_retry(ticker, period="1mo", interval="1h")
        )

        if df_1d.empty or df_1h.empty:
            return pd.DataFrame()

        # Remove timezone to prevent merge errors
        df_1d.index = df_1d.index.tz_localize(None)
        df_1h.index = df_1h.index.tz_localize(None)

        # Flatten multiindex columns if present
        if isinstance(df_1d.columns, pd.MultiIndex):
            df_1d.columns = [c[0] for c in df_1d.columns]
        if isinstance(df_1h.columns, pd.MultiIndex):
            df_1h.columns = [c[0] for c in df_1h.columns]

        import pandas_ta as ta
        # PRE-CALCULATE DAILY INDICATORS BEFORE MERGING
        # This ensures a 50-period EMA means 50 DAYS, not 50 hours!
        df_1d['EMA_50'] = ta.ema(df_1d['Close'], length=50)
        macd_1d = ta.macd(df_1d['Close'], fast=12, slow=26, signal=9)
        if macd_1d is not None and not macd_1d.empty:
            df_1d['MACD'] = macd_1d.iloc[:, 0]

        # Shift the daily data by 1 to completely eliminate Lookahead Bias.
        # This ensures that for any hour today, we only look at YESTERDAY'S fully closed daily candle.
        df_1d_shifted = df_1d.shift(1)

        # Rename daily columns so they don't clash with hourly columns
        df_1d_shifted.columns = [f"{c}_1d" for c in df_1d_shifted.columns]

        # Merge hourly data with the *previous* day's closed daily data
        df_merged = pd.merge_asof(df_1h, df_1d_shifted, left_index=True, right_index=True, direction='backward')

        df_merged.ffill(inplace=True)
        df_merged.dropna(inplace=True)

        return df_merged
    except Exception as e:
        logger.error(f"MTF data alignment error for {ticker}: {e}")
        return pd.DataFrame()
