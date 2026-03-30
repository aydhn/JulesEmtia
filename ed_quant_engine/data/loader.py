import yfinance as yf
import pandas as pd
import time
from core.logger import get_logger

log = get_logger()

def fetch_data(ticker, interval, period='2y', retries=3):
    for i in range(retries):
        try:
            df = yf.download(ticker, interval=interval, period=period, progress=False)
            if df.empty:
                log.warning(f"Empty DataFrame for {ticker} ({interval}). Retrying...")
                time.sleep(2 ** i)
                continue

            # yfinance returns multi-index columns sometimes, flatten them
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            df.dropna(inplace=True)
            return df
        except Exception as e:
            log.error(f"Error fetching data for {ticker} ({interval}): {e}. Retrying...")
            time.sleep(2 ** i)
    log.critical(f"Failed to fetch data for {ticker} after {retries} retries.")
    return pd.DataFrame()
