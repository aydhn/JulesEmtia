import yfinance as yf
import pandas as pd
import numpy as np
import time
from typing import Dict, Optional, Tuple

from core.logger import logger
from data_engine.config import TICKERS, MACRO_TICKERS

class DataEngine:
    """Yfinance MTF ve VIX Veri Motoru. Lookahead Bias olmadan çalışır."""

    def __init__(self):
        self.max_retries = 3
        self.backoff_factor = 2  # Exponential backoff
        self.current_vix = 0.0

    def _fetch_with_retry(self, ticker: str, interval: str, period: str) -> pd.DataFrame:
        """Rate limit'lere karşı exponential backoff kullanan veri çekim fonksiyonu."""
        for attempt in range(self.max_retries):
            try:
                data = yf.download(ticker, period=period, interval=interval, progress=False, show_errors=False)
                if not data.empty:
                    # Multi-index sütunlarını temizle
                    if isinstance(data.columns, pd.MultiIndex):
                        data.columns = [col[0] for col in data.columns]

                    # NaN Değerleri Temizle (Forward Fill)
                    data.fillna(method='ffill', inplace=True)
                    data.dropna(inplace=True)
                    return data
            except Exception as e:
                logger.warning(f"[{ticker}] Veri çekme hatası (Deneme {attempt+1}/{self.max_retries}): {e}")
                time.sleep(self.backoff_factor ** attempt)

        logger.error(f"[{ticker}] Veri Çekilemedi! (Maksimum deneme aşıldı.)")
        return pd.DataFrame()

    def fetch_htf_ltf(self, ticker_symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """MTF (Çoklu Zaman Dilimi): Günlük (HTF) ve Saatlik (LTF) verileri çeker."""
        # Günlük Trend (Son 2 Yıl)
        df_htf = self._fetch_with_retry(ticker_symbol, interval="1d", period="2y")
        # Saatlik Sinyal (Son 6 Ay - Maksimum Yfinance Saatlik Periyot Sınırı)
        df_ltf = self._fetch_with_retry(ticker_symbol, interval="1h", period="730d") # yf 1h limiti

        return df_htf, df_ltf

    def fetch_all_market_data(self) -> Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]:
        """Tüm evreni (HTF ve LTF) tarar. Döngüleri bloklamamak için basit iterasyon kullanır."""
        logger.info("Evren Verisi (HTF/LTF) çekilmeye başlandı...")
        market_data = {}
        for name, symbol in TICKERS.items():
            df_htf, df_ltf = self.fetch_htf_ltf(symbol)
            if not df_htf.empty and not df_ltf.empty:
                market_data[name] = (df_htf, df_ltf)
        logger.info(f"{len(market_data)} adet Ticker verisi başarıyla çekildi.")
        return market_data

    def fetch_macro_data(self) -> Dict[str, pd.DataFrame]:
        """DXY (Dolar Endeksi), TNX (10 Yıllık ABD Tahvili) ve VIX (Korku Endeksi) çeker."""
        macro_data = {}
        for name, symbol in MACRO_TICKERS.items():
            df = self._fetch_with_retry(symbol, interval="1d", period="1y")
            if not df.empty:
                macro_data[name] = df
                if name == "VIX":
                    self.current_vix = df['Close'].iloc[-1]

        logger.info(f"Makro Ekonomik Veriler Güncellendi. Güncel VIX: {self.current_vix:.2f}")
        return macro_data

    def check_flash_crash_anomaly(self, df_ltf: pd.DataFrame, window: int = 20, threshold: float = 4.0) -> bool:
        """
        Z-Score tabanlı mikro flaş çöküş tespiti (Siyah Kuğu).
        Son kapanan mum, hareketli ortalamasından 4-5 standart sapma uzaklaştıysa True döndürür.
        """
        if len(df_ltf) < window:
            return False

        closes = df_ltf['Close'].values
        rolling_mean = np.mean(closes[-window:])
        rolling_std = np.std(closes[-window:])

        if rolling_std == 0:
            return False

        last_close = closes[-1]
        z_score = (last_close - rolling_mean) / rolling_std

        # Anomali: -4 veya +4 Z-Score (Muazzam bir volatilite patlaması)
        if abs(z_score) >= threshold:
            logger.critical(f"FLASH CRASH TESPİT EDİLDİ! Z-Score: {z_score:.2f}")
            return True

        return False
