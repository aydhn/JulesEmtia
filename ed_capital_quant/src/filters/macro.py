import yfinance as yf
import pandas as pd
import numpy as np
from src.core.logger import logger
from src.core.config import VIX_THRESHOLD, Z_SCORE_ANOMALY

class MacroFilter:
    def __init__(self):
        self._vix_threshold = VIX_THRESHOLD
        self._z_score_threshold = Z_SCORE_ANOMALY

    def check_vix_circuit_breaker(self) -> bool:
        """
        Checks if the ^VIX (Volatility Index) is above the threshold, declaring a Black Swan.
        Returns True if safe, False if circuit breaker is triggered.
        """
        try:
            vix = yf.download("^VIX", period="5d", interval="1d", progress=False)
            if vix.empty:
                logger.warning("VIX data missing, assuming safe (with caution).")
                return True

            latest_vix = vix['Close'].iloc[-1].item() if not vix['Close'].empty else 0.0
            logger.info(f"Current VIX Level: {latest_vix:.2f}")

            if latest_vix >= self._vix_threshold:
                logger.critical(f"VIX Circuit Breaker Triggered: {latest_vix} >= {self._vix_threshold}. Halting new positions.")
                return False

            return True
        except Exception as e:
            logger.error(f"Error checking VIX: {e}")
            return True

    def is_z_score_anomalous(self, df: pd.DataFrame, window: int = 50) -> bool:
        """
        Calculates rolling Z-Score to detect flash crashes.
        Returns True if anomalous (Z-Score > threshold).
        """
        if len(df) < window:
            return False

        close = df['Close']
        rolling_mean = close.rolling(window=window).mean()
        rolling_std = close.rolling(window=window).std()

        # Calculate current z-score
        z_score = (close.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1]

        if abs(z_score) >= self._z_score_threshold:
            logger.critical(f"Flash Crash Detected! Z-Score: {z_score:.2f} >= {self._z_score_threshold}")
            return True

        return False

    def check_market_regime(self, ticker: str, direction: str) -> bool:
        """
        Checks macroeconomic regime based on DXY (US Dollar Index) and US 10-Year Treasury Yield (^TNX).
        Returns True if the regime allows the trade, False if vetoed.
        """
        try:
            # Fetch DXY and TNX
            dxy = yf.download("DX-Y.NYB", period="60d", interval="1d", progress=False)
            tnx = yf.download("^TNX", period="60d", interval="1d", progress=False)

            if dxy.empty or tnx.empty:
                logger.warning("Macro data (DXY/TNX) missing, assuming neutral regime.")
                return True

            dxy_close = dxy['Close'].squeeze()
            tnx_close = tnx['Close'].squeeze()

            # Simple SMA 50 calculation for trend
            dxy_sma50 = dxy_close.rolling(window=50).mean().iloc[-1]
            tnx_sma50 = tnx_close.rolling(window=50).mean().iloc[-1]

            dxy_current = dxy_close.iloc[-1]
            tnx_current = tnx_close.iloc[-1]

            dxy_uptrend = dxy_current > dxy_sma50
            tnx_uptrend = tnx_current > tnx_sma50

            is_tightening = dxy_uptrend and tnx_uptrend

            # Veto Logic
            # Example: If tightening (strong USD and high yields), Gold (GC=F) Longs are risky
            if is_tightening and ticker in ["GC=F", "SI=F"] and direction == "Long":
                logger.warning(f"Macro Veto: {ticker} Long blocked due to Tightening Regime (DXY & TNX Uptrend).")
                return False

            logger.debug(f"Macro Regime Confluence: {ticker} {direction} allowed.")
            return True

        except Exception as e:
            logger.error(f"Error checking market regime: {e}")
            return True # Fail open to avoid halting system on data errors

if __name__ == "__main__":
    mf = MacroFilter()
    print("Regime Safe:", mf.check_market_regime("GC=F", "Long"))
