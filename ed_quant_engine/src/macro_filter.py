import yfinance as yf
import pandas as pd
from src.logger import get_logger

logger = get_logger("macro_filter")

def fetch_macro_regime() -> dict:
    """Fetches DXY, US 10-Yr Yield, and VIX to determine market regime and swan events."""
    try:
        tickers = ["DX-Y.NYB", "^TNX", "^VIX"]
        # Use simple progress=False synchronous fetch to quickly grab yesterday's close
        df = yf.download(tickers, period="6mo", interval="1d", progress=False)['Close']
        df = df.ffill().dropna()

        if df.empty:
            logger.warning("Failed to fetch macro regime data.")
            return {"Regime": "Neutral", "VIX_Spike": False}

        # Calculate recent momentum to determine Regime
        dxy = df["DX-Y.NYB"]
        tnx = df["^TNX"]
        vix = df["^VIX"]

        dxy_50sma = dxy.rolling(window=50).mean().iloc[-1]
        dxy_current = dxy.iloc[-1]

        tnx_50sma = tnx.rolling(window=50).mean().iloc[-1]
        tnx_current = tnx.iloc[-1]

        # VIX Panic Detector
        vix_current = vix.iloc[-1]
        vix_prev = vix.iloc[-2]

        vix_spike = (vix_current > 30) or (vix_current > vix_prev * 1.25) # >25% daily jump

        regime = "Neutral"
        # If DXY and TNX are rising, Risk-Off (Tightening)
        if dxy_current > dxy_50sma and tnx_current > tnx_50sma:
            regime = "Risk-Off"
        # If DXY and TNX are falling, Risk-On (Easing)
        elif dxy_current < dxy_50sma and tnx_current < tnx_50sma:
            regime = "Risk-On"

        if vix_spike:
            logger.critical(f"VIX Spike Detected ({vix_current:.2f})! Black Swan protection engaged.")

        return {
            "Regime": regime,
            "DXY": dxy_current,
            "TNX": tnx_current,
            "VIX": vix_current,
            "VIX_Spike": vix_spike
        }
    except Exception as e:
        logger.error(f"Error fetching macro regime: {e}")
        return {"Regime": "Neutral", "VIX_Spike": False}

def apply_macro_veto(signal: str, regime: str, ticker: str) -> bool:
    """Returns True if the signal is VETOED based on macroeconomic conditions."""
    if signal == "Long" and regime == "Risk-Off" and ticker in ["GC=F", "SI=F", "EURTRY=X"]:
        logger.info(f"VETOED Long {ticker} due to Risk-Off (Strong USD/Yields) Regime.")
        return True
    return False
