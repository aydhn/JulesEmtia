import yfinance as yf
import pandas as pd
from logger import setup_logger

logger = setup_logger("MacroFilter")

async def get_macro_regime() -> str:
    """Calculates current global macro regime using DXY and 10Y Yields to avoid false positives in signal generation."""
    try:
        dxy = yf.download("DX-Y.NYB", period="60d", interval="1d", progress=False)
        tnx = yf.download("^TNX", period="60d", interval="1d", progress=False)

        if dxy.empty or tnx.empty:
            logger.warning("Makroekonomik veriler çekilemedi, Veto uygulanamıyor.")
            return "Neutral"

        # Calculate 50 SMA for both to determine trend
        dxy['SMA_50'] = dxy['Close'].rolling(window=50).mean()
        tnx['SMA_50'] = tnx['Close'].rolling(window=50).mean()

        last_dxy = dxy['Close'].iloc[-1]
        sma_dxy = dxy['SMA_50'].iloc[-1]

        last_tnx = tnx['Close'].iloc[-1]
        sma_tnx = tnx['SMA_50'].iloc[-1]

        # Risk-Off Regime: Both DXY and Yields are trending up (Strong Headwinds for Gold/EM Currencies)
        if last_dxy > sma_dxy and last_tnx > sma_tnx:
            logger.info("Makro Rejim: Risk-Off (DXY ve Tahvil Yüksek)")
            return "Risk-Off"

        # Risk-On Regime: Both trending down
        elif last_dxy < sma_dxy and last_tnx < sma_tnx:
            logger.info("Makro Rejim: Risk-On (DXY ve Tahvil Düşük)")
            return "Risk-On"

        return "Neutral"
    except Exception as e:
        logger.error(f"Makro filtre hesaplama hatası: {str(e)}")
        return "Neutral"

async def check_vix_circuit_breaker() -> bool:
    """A Black Swan / Flash Crash protection mechanism. Vetoes all new trades if VIX is spiking."""
    try:
        vix = yf.download("^VIX", period="5d", interval="1d", progress=False)
        if vix.empty:
            return False

        current_vix = vix['Close'].iloc[-1]
        previous_vix = vix['Close'].iloc[-2]

        spike_pct = ((current_vix - previous_vix) / previous_vix) * 100

        # Absolute threshold (e.g., > 30) or relative spike (e.g., > 20% in one day)
        if current_vix > 30 or spike_pct > 20:
            logger.critical(f"🚨 SİYAH KUĞU DEVRE KESİCİ TETİKLENDİ 🚨 VIX: {current_vix:.2f} (+%{spike_pct:.2f})")
            return True # Halt trading

        return False
    except Exception as e:
        logger.error(f"VIX monitör hatası: {str(e)}")
        return False

def check_z_score_anomaly(prices: pd.Series, window: int = 50, threshold: float = 4.0) -> bool:
    """Micro Flash Crash detector. Checks if current price is a 4+ standard deviation outlier."""
    if len(prices) < window:
        return False

    mean = prices.rolling(window).mean().iloc[-1]
    std = prices.rolling(window).std().iloc[-1]
    current = prices.iloc[-1]

    if std == 0:
        return False

    z_score = abs(current - mean) / std
    if z_score > threshold:
        logger.critical(f"Mikro Flaş Çöküş (Anomali) Tespit Edildi! Z-Score: {z_score:.2f}")
        return True # Halt trading for this ticker

    return False
