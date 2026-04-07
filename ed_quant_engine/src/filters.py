import yfinance as yf
import pandas as pd
import numpy as np
from .logger import quant_logger
import asyncio

class MarketFilters:
    @staticmethod
    async def get_vix_status(threshold: float = 30.0) -> bool:
        """
        Check if VIX is above threshold. True means Black Swan / Panic mode (No new longs).
        """
        try:
            vix = await asyncio.to_thread(yf.download, tickers='^VIX', period='5d', interval='1d', progress=False)
            if vix.empty:
                return False

            if isinstance(vix.columns, pd.MultiIndex):
                vix.columns = [col[0] for col in vix.columns]

            last_vix_close = vix['Close'].iloc[-1]
            is_panic = last_vix_close > threshold
            if is_panic:
                quant_logger.critical(f"VIX CIRCUIT BREAKER ACTIVATED! VIX Level: {last_vix_close:.2f}")
            return is_panic
        except Exception as e:
            quant_logger.error(f"VIX check failed: {e}")
            return False

    @staticmethod
    def check_flash_crash(df: pd.DataFrame, z_threshold: float = -4.0) -> bool:
        """
        Micro anomaly detection. Returns True if current close is highly deviated.
        """
        try:
            if len(df) < 50:
                return False
            mean_50 = df['Close'].rolling(50).mean().iloc[-1]
            std_50 = df['Close'].rolling(50).std().iloc[-1]
            current_close = df['Close'].iloc[-1]

            z_score = (current_close - mean_50) / std_50
            if z_score <= z_threshold:
                quant_logger.warning(f"FLASH CRASH DETECTED! Z-Score: {z_score:.2f}")
                return True
            return False
        except Exception as e:
            quant_logger.error(f"Flash crash detection failed: {e}")
            return False

    @staticmethod
    async def check_macro_regime() -> str:
        """
        Determine regime based on DXY and 10Y Yields.
        Returns 'Risk-On', 'Risk-Off', or 'Neutral'
        """
        try:
            # Fetch DXY (DX-Y.NYB) and US10Y (^TNX)
            dxy = await asyncio.to_thread(yf.download, tickers='DX-Y.NYB', period='50d', progress=False)
            tnx = await asyncio.to_thread(yf.download, tickers='^TNX', period='50d', progress=False)

            # Simple regime logic: if both are above 50 SMA, it's tightening (Risk-Off)
            dxy_close = dxy['Close'].iloc[-1] if not isinstance(dxy.columns, pd.MultiIndex) else dxy['Close'].iloc[-1].iloc[0]
            dxy_sma = dxy['Close'].mean() if not isinstance(dxy.columns, pd.MultiIndex) else dxy['Close'].mean().iloc[0]

            tnx_close = tnx['Close'].iloc[-1] if not isinstance(tnx.columns, pd.MultiIndex) else tnx['Close'].iloc[-1].iloc[0]
            tnx_sma = tnx['Close'].mean() if not isinstance(tnx.columns, pd.MultiIndex) else tnx['Close'].mean().iloc[0]

            if dxy_close > dxy_sma and tnx_close > tnx_sma:
                return "Risk-Off"
            elif dxy_close < dxy_sma and tnx_close < tnx_sma:
                return "Risk-On"
            return "Neutral"

        except Exception as e:
            quant_logger.error(f"Macro regime check failed: {e}")
            return "Neutral"
