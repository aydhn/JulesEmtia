import pandas_ta as ta
import pandas as pd
import numpy as np
import asyncio
from typing import Dict, Any

from core.logger import logger
from strategy.quant_math import QuantMath
from strategy.ml_validator import MLValidator
from data_engine.nlp_sentiment import NLPSentimentFilter

class StrategyEngine:
    """Tüm analizlerin birleştiği Ana Karar Motoru (Sinyal Fabrikası)."""

    def __init__(self):
        self.quant_math = QuantMath()
        self.ml_validator = MLValidator()
        self.nlp_filter = NLPSentimentFilter()

    def add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sıfır Lookahead Bias ile teknik indikatörleri hesaplar."""
        df_ind = df.copy()

        # Trend (Ana Yön)
        df_ind['EMA_50'] = ta.ema(df_ind['Close'], length=50)
        df_ind['EMA_200'] = ta.ema(df_ind['Close'], length=200)

        # Momentum & Aşırı Alım/Satım
        df_ind['RSI_14'] = ta.rsi(df_ind['Close'], length=14)
        macd = ta.macd(df_ind['Close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df_ind = pd.concat([df_ind, macd], axis=1)

        # Volatilite & Risk
        df_ind['ATR_14'] = ta.atr(df_ind['High'], df_ind['Low'], df_ind['Close'], length=14)
        bbands = ta.bbands(df_ind['Close'], length=20, std=2)
        if bbands is not None and not bbands.empty:
            df_ind = pd.concat([df_ind, bbands], axis=1)

        # Geçmişteki (Shift=1) değerleri almalıyız ki anlık değişime aldanmayalım (Lookahead Koruması)
        for col in df_ind.columns:
            if col not in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df_ind[col] = df_ind[col].shift(1)

        return df_ind.dropna()

    async def generate_signal_async(self, df_htf: pd.DataFrame, df_ltf: pd.DataFrame, ticker: str, current_vix: float) -> Dict[str, Any]:
        """
        Asenkron NLP desteğiyle MTF (Günlük ve Saatlik) birleşimi ve Çoklu Onay (Confluence) mekanizmasıyla sinyal üretir.
        """
        if df_ltf.empty or df_htf.empty:
            return {"signal": 0} # No Signal

        # İndikatörleri Hesapla
        htf = self.add_features(df_htf)
        ltf = self.add_features(df_ltf)

        if len(ltf) < 200 or len(htf) < 200:
            return {"signal": 0} # Yeterli veri yok

        # 1. SİYAH KUĞU KORUMASI (VIX DEVRE KESİCİSİ)
        if current_vix > 30.0:
            logger.warning(f"DEVRE KESİCİ AÇIK: VIX={current_vix:.2f} > 30. Yeni İşlem Kapatıldı!")
            return {"signal": 0} # Sinyal Üretme

        # En son kapanan (Shift(1) ile korunan) LTF (Saatlik) mum verileri
        last_ltf = ltf.iloc[-1]

        # En son kapanan HTF (Günlük) mum verileri (MTF Hizalaması)
        last_ltf_time = ltf.index[-1]
        valid_htf = htf[htf.index < last_ltf_time]
        if valid_htf.empty:
             return {"signal": 0}
        last_htf = valid_htf.iloc[-1]

        signal = 0 # Nötr
        direction = ""

        # ---- LONG (ALIM) SENARYOSU ----
        # 1. MTF Trend Onayı (Günlük EMA50'nin Üzerinde mi?)
        htf_bullish = last_htf['Close'] > last_htf['EMA_50']

        # 2. LTF Tetikleyici (Saatlik RSI Aşırı Satımdan dönüyor mu veya Alt Banda Değdi mi?)
        ltf_bullish_rsi = (last_ltf['RSI_14'] < 30) or (ltf.iloc[-2]['RSI_14'] < 30 and last_ltf['RSI_14'] > 30)
        bbl_col = [c for c in ltf.columns if c.startswith('BBL')]
        ltf_bullish_bb = (last_ltf['Low'] <= last_ltf[bbl_col[0]]) if bbl_col else False

        if htf_bullish and (ltf_bullish_rsi or ltf_bullish_bb):
            signal = 1
            direction = "Long"

        # ---- SHORT (SATIŞ) SENARYOSU ----
        # Tam tersi
        htf_bearish = last_htf['Close'] < last_htf['EMA_50']
        ltf_bearish_rsi = (last_ltf['RSI_14'] > 70) or (ltf.iloc[-2]['RSI_14'] > 70 and last_ltf['RSI_14'] < 70)
        bbu_col = [c for c in ltf.columns if c.startswith('BBU')]
        ltf_bearish_bb = (last_ltf['High'] >= last_ltf[bbu_col[0]]) if bbu_col else False

        if htf_bearish and (ltf_bearish_rsi or ltf_bearish_bb):
            signal = -1
            direction = "Short"

        # VETO KONTROLLERİ (Teknik Sinyal Onaylandıysa Sıradakine Geç)
        if signal != 0:
            # 1. Asenkron NLP Sentiment Vetosu
            is_vetoed = await self.nlp_filter.sentiment_veto_async(ticker, direction, threshold=0.50)
            if is_vetoed:
                return {"signal": 0} # Veto yedi

            # 2. ML (Yapay Zeka) Doğrulaması
            features = np.array([
                last_ltf['RSI_14'],
                last_ltf['ATR_14'],
                last_ltf['Close'] / last_ltf['EMA_50'] - 1, # Fiyatın Ortalamaya Uzaklığı
                last_htf['RSI_14']
            ])
            if not self.ml_validator.validate_signal(features):
                return {"signal": 0} # ML Vetosu yedi

            # 3. JP Morgan Risk & Maliyet Hesaplaması (Dinamik Stop ve Lot)
            entry_price = last_ltf['Close']
            atr = last_ltf['ATR_14']

            if direction == "Long":
                sl_price = entry_price - (1.5 * atr)
                tp_price = entry_price + (3.0 * atr)
            else:
                sl_price = entry_price + (1.5 * atr)
                tp_price = entry_price - (3.0 * atr)

            avg_atr = ltf['ATR_14'].mean()
            fees = self.quant_math.calculate_dynamic_execution_cost(ticker, entry_price, atr, avg_atr)

            logger.info(f"YENİ SİNYAL: [{ticker}] YÖN: {direction} (Giriş: {entry_price:.4f}, SL: {sl_price:.4f}, TP: {tp_price:.4f}, Maliyet: {fees:.4f})")

            return {
                "signal": signal,
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry_price,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "fees": fees,
                "atr": atr
            }

        return {"signal": 0}

    # Eski senkron metod geriye dönük uyumluluk (Örn: Backtest için)
    def generate_signal(self, df_htf: pd.DataFrame, df_ltf: pd.DataFrame, ticker: str, current_vix: float) -> Dict[str, Any]:
        """Senkron Sinyal Üretimi (Backtest için)."""
        return asyncio.run(self.generate_signal_async(df_htf, df_ltf, ticker, current_vix))