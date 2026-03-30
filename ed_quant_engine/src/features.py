import pandas as pd
import pandas_ta as ta
import numpy as np

def add_features(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
    """
    Verilen DataFrame'e teknik göstergeleri (RSI, MACD, EMA, ATR, BB) ekler.
    is_htf=True ise, üst zaman dilimine ait (Günlük) daha dar bir set hesaplanabilir.
    """
    if df is None or len(df) < 250: # En az 200 EMA için veri lazım
        return df

    df = df.copy()

    # 1. Trend Filtreleri (Ana Yön)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)

    # 2. Momentum & Aşırı Alım/Satım
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    # 3. Volatilite & Risk (JP Morgan)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)

    # 4. Price Action
    df['Returns'] = df['Close'].pct_change()

    # Sinyal Üretiminde "Geleceği Görme" (Lookahead Bias) olmaması için
    # hesaplanan TÜM göstergeleri 1 satır kaydır (shift).
    # Bu sayede bugünün kapanış kararı dünkü verilere dayanır.
    # Ancak Fiyatları yerinde tutacağız (Anlık Kar/Zarar takibi için)
    # Strateji modülünde .shift(1) uygulanmış kolonlar dikkate alınacaktır.

    # NaN Yönetimi: EMA200 ve MACD için boşluklar
    df.dropna(inplace=True)

    return df

def merge_mtf_data(df_ltf: pd.DataFrame, df_htf: pd.DataFrame) -> pd.DataFrame:
    """
    HTF (Günlük) veriyi LTF (Saatlik) veriye 'Lookahead Bias' olmadan bağlar.
    Günlük göstergeler (HTF), saatlik kapanışlara karar vermek için kullanılır.
    """
    # 1. HTF Verisinde 'Tarih' (index) günlüğe çevrili olabilir.
    df_htf = df_htf.copy()

    # Önce HTF (Günlük) verideki indikatörleri suffix ile isimlendir.
    htf_cols = [c for c in df_htf.columns if c not in ['Open', 'High', 'Low', 'Close', 'Volume']]
    df_htf_indicators = df_htf[htf_cols].copy()
    df_htf_indicators.columns = [f"HTF_{c}" for c in df_htf_indicators.columns]

    # LOOKAHEAD BIAS KORUMASI: Günlük mum, ancak GÜN BİTTİĞİNDE bilinir.
    # Bu yüzden günlük verileri tam 1 gün geriye itiyoruz (shift(1)).
    # Yani 15:00'da saatlik mum kapanırken, "DÜNKÜ" günlük göstergeye bakacağız.
    df_htf_shifted = df_htf_indicators.shift(1)

    # 2. LTF (Saatlik) veriyle merge_asof kullanarak backward join yapıyoruz.
    # Asof, zaman damgalarını geriye doğru en yakın olana eşleştirir.
    df_merged = pd.merge_asof(
        df_ltf,
        df_htf_shifted,
        left_index=True,
        right_index=True,
        direction='backward'
    )

    return df_merged
