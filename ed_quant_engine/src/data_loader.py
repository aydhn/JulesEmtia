import yfinance as yf
import pandas as pd
import numpy as np
import time
import asyncio
from typing import Dict, List, Optional
from .logger import log_info, log_error, log_warning

def fetch_data_sync(ticker: str, period: str = "60d", interval: str = "1h", retries: int = 3) -> Optional[pd.DataFrame]:
    """
    yfinance üzerinden veri çeken Exponential Backoff korumalı senkron metod.
    """
    for attempt in range(retries):
        try:
            df = yf.download(ticker, period=period, interval=interval, progress=False)
            if df.empty:
                log_warning(f"[{ticker}] Veri boş döndü. (Deneme {attempt+1}/{retries})")
                time.sleep(2 ** attempt)
                continue

            # Eğer columns MultiIndex ise (yfinance 0.2.37 bazen yapabiliyor), Flatten
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            # Nan yönetimi (Forward fill) ve indeks temizliği
            df.ffill(inplace=True)
            df.dropna(inplace=True) # İlk satırlardaki temizlenemeyen nan'lar için
            df.index = df.index.tz_localize(None) # Zaman dilimi tutarsızlığını önlemek için tz strip
            return df
        except Exception as e:
            log_error(f"[{ticker}] API Hatası: {e} (Deneme {attempt+1}/{retries})")
            time.sleep(2 ** attempt)

    log_error(f"[{ticker}] Veri çekilemedi. Max retry sayısına ulaşıldı.")
    return None

async def fetch_data_async(ticker: str, period: str = "60d", interval: str = "1h", retries: int = 3) -> Optional[pd.DataFrame]:
    """
    Senkron metodu asyncio evreninde bloklamadan çalıştıran Async Wrapper.
    """
    return await asyncio.to_thread(fetch_data_sync, ticker, period, interval, retries)

async def load_universe_mtf(tickers: List[str]) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Tüm evrenin Günlük (HTF) ve Saatlik (LTF) verilerini asenkron olarak çeker.
    Dönüş formatı: {"GC=F": {"1d": df_daily, "1h": df_hourly}}
    """
    log_info(f"{len(tickers)} adet varlık için MTF (1D ve 1H) veri çekimi başlatılıyor...")
    universe_data = {}

    # İki ayrı görev listesi
    tasks_1d = [fetch_data_async(t, period="2y", interval="1d") for t in tickers]
    tasks_1h = [fetch_data_async(t, period="60d", interval="1h") for t in tickers]

    # Asenkron bekleme
    results_1d = await asyncio.gather(*tasks_1d)
    results_1h = await asyncio.gather(*tasks_1h)

    # Sözlüğe doldurma
    for i, ticker in enumerate(tickers):
        if results_1d[i] is not None and results_1h[i] is not None:
            universe_data[ticker] = {
                "1d": results_1d[i],
                "1h": results_1h[i]
            }
        else:
            log_warning(f"[{ticker}] MTF verileri eksik olduğu için işleme alınmayacak.")

    log_info(f"{len(universe_data)} varlığın MTF verisi başarıyla çekildi.")
    return universe_data
