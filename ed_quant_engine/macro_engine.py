import yfinance as yf
import pandas as pd
from typing import Dict, Any
from logger import get_logger

logger = get_logger("macro_engine")

def get_vix_level() -> float:
    """Fetches the current S&P 500 VIX level."""
    try:
        vix = yf.download("^VIX", period="1d", progress=False)
        if not vix.empty:
            return float(vix['Close'].iloc[-1])
        return 0.0
    except Exception as e:
        logger.error(f"Failed to fetch VIX: {e}")
        return 0.0

def get_dxy_trend() -> Dict[str, Any]:
    """Fetches Dollar Index (DXY) to determine global risk sentiment."""
    try:
        dxy = yf.download("DX-Y.NYB", period="100d", progress=False)
        if not dxy.empty:
            dxy['SMA_50'] = dxy['Close'].rolling(window=50).mean()
            current_close = float(dxy['Close'].iloc[-1])
            sma_50 = float(dxy['SMA_50'].iloc[-1])

            trend = "Bullish" if current_close > sma_50 else "Bearish"
            return {"trend": trend, "value": current_close, "sma50": sma_50}
        return {"trend": "Neutral", "value": 0.0, "sma50": 0.0}
    except Exception as e:
        logger.error(f"Failed to fetch DXY: {e}")
        return {"trend": "Neutral", "value": 0.0, "sma50": 0.0}

def get_tnx_trend() -> Dict[str, Any]:
    """Fetches US 10-Year Treasury Yield (^TNX) to determine yield pressure."""
    try:
        tnx = yf.download("^TNX", period="100d", progress=False)
        if not tnx.empty:
            tnx['SMA_50'] = tnx['Close'].rolling(window=50).mean()
            current_close = float(tnx['Close'].iloc[-1])
            sma_50 = float(tnx['SMA_50'].iloc[-1])

            trend = "Rising" if current_close > sma_50 else "Falling"
            return {"trend": trend, "value": current_close, "sma50": sma_50}
        return {"trend": "Neutral", "value": 0.0, "sma50": 0.0}
    except Exception as e:
        logger.error(f"Failed to fetch TNX: {e}")
        return {"trend": "Neutral", "value": 0.0, "sma50": 0.0}

def determine_market_regime() -> str:
    """Determines the market regime based on VIX, DXY, and US10Y."""
    vix = get_vix_level()
    dxy = get_dxy_trend()
    tnx = get_tnx_trend()

    # Black Swan / Extreme Panic
    if vix > 35.0:
        logger.critical(f"BLACK SWAN REGIME DETECTED: VIX={vix:.2f}")
        return "Extreme Panic"

    # High Risk / Risk-Off
    if vix > 25.0 or (dxy["trend"] == "Bullish" and tnx["trend"] == "Rising"):
        logger.warning(f"RISK-OFF REGIME DETECTED: VIX={vix:.2f}, DXY={dxy['trend']}, US10Y={tnx['trend']}")
        return "Risk-Off"

    # Normal / Risk-On
    logger.info(f"RISK-ON REGIME DETECTED: VIX={vix:.2f}, DXY={dxy['trend']}, US10Y={tnx['trend']}")
    return "Risk-On"

if __name__ == "__main__":
    print(determine_market_regime())
