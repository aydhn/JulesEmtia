import yfinance as yf
import pandas as pd
from typing import Dict, Tuple
from core.logger import setup_logger
import asyncio

logger = setup_logger("macro_filter")

class MacroFilter:
    """
    Calculates the Market Regime using DXY and US10Y.
    Implements VIX Circuit Breakers and Z-Score Flash Crash protection.
    """
    def __init__(self):
        self.vix_ticker = "^VIX"
        self.dxy_ticker = "DX-Y.NYB"
        self.us10y_ticker = "^TNX"
        self.vix_critical_threshold = 30.0
        self.vix_spike_threshold_pct = 0.20 # 20% spike in 1 day

    async def get_macro_regime(self) -> str:
        """
        Returns Risk-On, Risk-Off, or Neutral based on DXY and TNX trends.
        """
        try:
            tickers = f"{self.dxy_ticker} {self.us10y_ticker}"
            df = await asyncio.to_thread(
                yf.download, tickers=tickers, period="6mo", interval="1d", progress=False
            )

            # Extract close prices
            if isinstance(df.columns, pd.MultiIndex):
                # We need 'Close' level
                closes = df['Close']
            else:
                return "Neutral" # Fallback

            closes.ffill(inplace=True)

            dxy_close = closes[self.dxy_ticker]
            tnx_close = closes[self.us10y_ticker]

            # Simple 50-day SMA regime filter
            dxy_sma50 = dxy_close.rolling(window=50).mean().iloc[-1]
            dxy_current = dxy_close.iloc[-1]

            tnx_sma50 = tnx_close.rolling(window=50).mean().iloc[-1]
            tnx_current = tnx_close.iloc[-1]

            if dxy_current > dxy_sma50 and tnx_current > tnx_sma50:
                logger.info("Macro Regime: RISK-OFF (Strong Dollar & Yields)")
                return "Risk-Off"
            elif dxy_current < dxy_sma50 and tnx_current < tnx_sma50:
                logger.info("Macro Regime: RISK-ON (Weak Dollar & Yields)")
                return "Risk-On"
            else:
                return "Neutral"

        except Exception as e:
            logger.error(f"Failed to calculate macro regime: {e}")
            return "Neutral"

    async def check_vix_circuit_breaker(self) -> bool:
        """
        Returns True if the VIX circuit breaker is tripped (Black Swan event).
        """
        try:
            df = await asyncio.to_thread(
                yf.download, tickers=self.vix_ticker, period="5d", interval="1d", progress=False
            )
            if df.empty:
                return False

            close_col = 'Close' if 'Close' in df.columns else df.columns[df.columns.get_level_values(0) == 'Close'][0]
            vix_series = df[close_col]
            if isinstance(vix_series, pd.DataFrame):
                vix_series = vix_series[self.vix_ticker]

            current_vix = vix_series.iloc[-1]
            prev_vix = vix_series.iloc[-2] if len(vix_series) > 1 else current_vix

            spike_pct = (current_vix - prev_vix) / prev_vix

            if current_vix >= self.vix_critical_threshold:
                logger.critical(f"VIX Circuit Breaker: Absolute Threshold Exceeded! VIX={current_vix:.2f}")
                return True

            if spike_pct >= self.vix_spike_threshold_pct:
                logger.critical(f"VIX Circuit Breaker: Spike Threshold Exceeded! VIX jumped {spike_pct*100:.1f}%")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check VIX: {e}")
            return False

    def detect_flash_crash(self, ltf_df: pd.DataFrame, window: int = 50, z_threshold: float = 4.0) -> bool:
        """
        Calculates Z-Score of the current price against a rolling window.
        Returns True if an anomaly (Flash Crash) is detected.
        """
        if len(ltf_df) < window:
            return False

        closes = ltf_df['close']
        current_price = closes.iloc[-1]

        # Calculate mean and std of the window excluding the current price to avoid skewing
        window_closes = closes.iloc[-window-1:-1]
        mean = window_closes.mean()
        std = window_closes.std()

        if std == 0:
            return False

        z_score = abs((current_price - mean) / std)

        if z_score >= z_threshold:
            logger.warning(f"Flash Crash Detected! Z-Score: {z_score:.2f}")
            return True

        return False
