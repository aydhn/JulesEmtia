import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from .logger import log_info, log_error, log_warning

def check_black_swan(df_vix: pd.DataFrame, threshold: float = 30.0) -> bool:
    """
    Siyah Kuğu/Devre Kesici Koruması.
    Eğer VIX belirlenen eşiğin üzerindeyse, piyasada panik var demektir.
    """
    if df_vix.empty:
        return False

    last_vix = df_vix['Close'].iloc[-1]
    if last_vix > threshold:
        log_warning(f"🚨 SİYAH KUĞU KORUMASI: VIX {last_vix:.2f} ile eşiği ({threshold}) aştı!")
        return True
    return False

def check_flash_crash(df: pd.DataFrame, window: int = 50, z_threshold: float = -4.0) -> bool:
    """
    Ani Çöküş Tespiti (Z-Score).
    Fiyat, hareketli ortalamasından aniden aşırı standart sapma kadar koptuysa.
    """
    if len(df) < window:
        return False

    prices = df['Close']
    ma = prices.rolling(window=window).mean()
    std = prices.rolling(window=window).std()

    z_score = (prices.iloc[-1] - ma.iloc[-1]) / std.iloc[-1]

    if z_score < z_threshold or z_score > abs(z_threshold):
        log_warning(f"🚨 FLAŞ ÇÖKÜŞ KORUMASI: Z-Score {z_score:.2f} anomalisi tespit edildi!")
        return True
    return False

def get_market_regime(df_dxy: pd.DataFrame, df_tnx: pd.DataFrame) -> str:
    """
    Risk-On / Risk-Off makro rejim belirleyicisi.
    Dolar Endeksi ve 10 Yıllık Tahvil getirisi trendde mi?
    """
    if df_dxy.empty or df_tnx.empty:
        return "Neutral"

    dxy_trend = df_dxy['Close'].iloc[-1] > df_dxy['Close'].rolling(50).mean().iloc[-1]
    tnx_trend = df_tnx['Close'].iloc[-1] > df_tnx['Close'].rolling(50).mean().iloc[-1]

    if dxy_trend and tnx_trend:
        # Dolar ve Faiz artıyor -> Altın/Riskli varlıklar için sıkılaşma rejimi (Risk-Off)
        return "Risk-Off"
    elif not dxy_trend and not tnx_trend:
        # Gevşeme rejimi (Risk-On)
        return "Risk-On"
    else:
        return "Neutral"
