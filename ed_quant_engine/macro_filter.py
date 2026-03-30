import yfinance as yf
import pandas as pd
import numpy as np
from logger import logger
import asyncio

class MacroFilter:
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self.tnx_ticker = "^TNX"
        self.vix_ticker = "^VIX"
        self.cache = {}

    async def fetch_macro_data(self):
        try:
            dxy, tnx = await asyncio.gather(
                asyncio.to_thread(yf.download, self.dxy_ticker, period="1mo", interval="1d", progress=False),
                asyncio.to_thread(yf.download, self.tnx_ticker, period="1mo", interval="1d", progress=False)
            )

            if not dxy.empty and not tnx.empty:
                # Forward fill NaNs
                self.cache['dxy_close'] = dxy['Close'].ffill().iloc[-1].item()
                self.cache['dxy_sma50'] = dxy['Close'].rolling(50).mean().iloc[-1].item() if len(dxy) >= 50 else self.cache['dxy_close']
                self.cache['tnx_close'] = tnx['Close'].ffill().iloc[-1].item()
                self.cache['tnx_sma50'] = tnx['Close'].rolling(50).mean().iloc[-1].item() if len(tnx) >= 50 else self.cache['tnx_close']

            logger.info("Macro data updated successfully.")
        except Exception as e:
            logger.error(f"Error fetching macro data: {e}")

    def get_regime(self) -> str:
        '''
        Phase 6: Market Regime Filter
        '''
        if not self.cache:
            return "Neutral"

        dxy = self.cache.get('dxy_close', 0)
        dxy_sma = self.cache.get('dxy_sma50', 0)
        tnx = self.cache.get('tnx_close', 0)
        tnx_sma = self.cache.get('tnx_sma50', 0)

        # Risk-Off / Tightening Regime: Strong DXY and rising yields
        if dxy > dxy_sma and tnx > tnx_sma:
            return "Risk-Off"
        # Risk-On / Loosening Regime: Weak DXY and falling yields
        elif dxy < dxy_sma and tnx < tnx_sma:
            return "Risk-On"

        return "Neutral"

    def veto_signal(self, ticker: str, direction: str) -> bool:
        '''
        Returns True if the signal should be vetoed based on macro regime.
        '''
        regime = self.get_regime()

        metals = ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"]
        em_fx = ["USDTRY=X", "EURTRY=X"] # Long EM means short USD effectively if trading TRY base

        # Phase 6: Counter-trend macro veto
        if regime == "Risk-Off":
             # Strong Dollar/Yields is bad for Gold/Silver longs
             if ticker in metals and direction == "Long":
                 logger.info(f"Macro Veto: {direction} {ticker} rejected due to Risk-Off regime (Strong DXY/TNX).")
                 return True

        return False

    async def check_vix_circuit_breaker(self, threshold=35.0) -> bool:
        '''
        Phase 19: Black Swan / VIX Circuit Breaker
        '''
        try:
            vix = await asyncio.to_thread(yf.download, self.vix_ticker, period="5d", interval="1d", progress=False)
            if vix.empty: return False

            last_vix = vix['Close'].iloc[-1].item()
            prev_vix = vix['Close'].iloc[-2].item() if len(vix) > 1 else last_vix

            # Absolute threshold or sudden >25% spike
            if last_vix > threshold or (last_vix > prev_vix * 1.25):
                logger.critical(f"BLACK SWAN: VIX at {last_vix:.2f}. Circuit Breaker Triggered!")
                return True
            return False
        except Exception as e:
            logger.error(f"VIX check error: {e}")
            return False

    def check_zscore_anomaly(self, df: pd.DataFrame, threshold=4.0) -> bool:
        '''
        Phase 19: Micro Flash Crash Detector
        '''
        if df.empty or len(df) < 20: return False
        try:
            prices = df['Close']
            mean = prices.rolling(20).mean().iloc[-1]
            std = prices.rolling(20).std().iloc[-1]

            if std == 0: return False

            current_price = prices.iloc[-1]
            z_score = abs((current_price - mean) / std)

            if z_score > threshold:
                logger.critical(f"FLASH CRASH ANOMALY: Z-Score {z_score:.2f} exceeds threshold {threshold}.")
                return True
            return False
        except Exception as e:
            logger.error(f"Z-Score anomaly check error: {e}")
            return False

macro_filter = MacroFilter()
