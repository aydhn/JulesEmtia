import yfinance as yf
import pandas as pd
import time
from core.logger import logger

class DataLoader:
    @staticmethod
    def fetch_data(ticker: str, timeframe: str = "1h", period: str = "1y", retries=3) -> pd.DataFrame:
        for attempt in range(retries):
            try:
                df = yf.download(ticker, period=period, interval=timeframe, progress=False)
                if df.empty:
                    raise ValueError(f"{ticker} için boş veri döndü.")
                df.ffill(inplace=True)
                return df
            except Exception as e:
                sleep_time = 2 ** attempt
                logger.warning(f"{ticker} veri çekilemedi. {sleep_time} sn bekleniyor... Hata: {e}")
                time.sleep(sleep_time)
        logger.error(f"{ticker} için veri çekimi {retries} denemede başarısız.")
        return pd.DataFrame()

    @staticmethod
    def get_mtf_data(ticker: str):
        df_1h = DataLoader.fetch_data(ticker, "1h", "1y")
        df_1d = DataLoader.fetch_data(ticker, "1d", "2y")
        if df_1h.empty or df_1d.empty: return None

        df_1d_shifted = df_1d.shift(1).copy()
        df_1d_shifted.columns = [f"D1_{c[0]}" if isinstance(c, tuple) else f"D1_{c}" for c in df_1d_shifted.columns]

        df_1h.index = df_1h.index.tz_localize(None)
        df_1d_shifted.index = df_1d_shifted.index.tz_localize(None)

        merged = pd.merge_asof(df_1h, df_1d_shifted, left_index=True, right_index=True, direction='backward')
        return merged
