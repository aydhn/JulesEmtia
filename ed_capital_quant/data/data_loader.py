import yfinance as yf
import pandas as pd
import time
from utils.logger import log

def fetch_data_with_retry(ticker: str, interval: str, period: str = "60d") -> pd.DataFrame:
    for attempt in range(3):
        try:
            df = yf.download(ticker, interval=interval, period=period, progress=False)
            if df.empty: raise ValueError("Boş Veri")
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            df.ffill(inplace=True)
            return df
        except Exception as e:
            log.warning(f"{ticker} veri çekilemedi (Deneme {attempt+1}): {e}")
            time.sleep(2 ** attempt)
    return pd.DataFrame()

def get_mtf_data(ticker: str) -> pd.DataFrame:
    df_ltf = fetch_data_with_retry(ticker, "1h", period="60d")
    df_htf = fetch_data_with_retry(ticker, "1d", period="100d")

    if df_ltf.empty or df_htf.empty: return pd.DataFrame()

    df_htf_shifted = df_htf.shift(1).add_suffix('_HTF')

    df_ltf = df_ltf.reset_index()
    df_htf_shifted = df_htf_shifted.reset_index()

    if 'Datetime' in df_ltf.columns and 'Date' in df_htf_shifted.columns:
        df_ltf['Datetime'] = pd.to_datetime(df_ltf['Datetime']).dt.tz_localize(None)
        df_htf_shifted['Date'] = pd.to_datetime(df_htf_shifted['Date']).dt.tz_localize(None)
        df_merged = pd.merge_asof(df_ltf.sort_values('Datetime'), df_htf_shifted.sort_values('Date'), left_on='Datetime', right_on='Date', direction='backward')
        return df_merged.set_index('Datetime')
    return df_ltf.set_index(df_ltf.columns[0]) if not df_ltf.empty else pd.DataFrame()
