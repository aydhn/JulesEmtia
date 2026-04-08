import yfinance as yf
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class MacroFilter:
    """
    Phase 19: Black Swan, VIX Circuit Breaker, Flash Crash (Z-Score)
    Phase 6: Macro Regime (DXY, Yields)
    """
    def __init__(self, vix_threshold: float = 35.0, z_score_threshold: float = 4.0):
        self.vix_threshold = vix_threshold
        self.z_score_threshold = z_score_threshold
        self.macro_data = {}

    def is_black_swan(self) -> bool:
        """Checks VIX for extreme panic conditions."""
        try:
            vix = yf.download("^VIX", period="5d", progress=False)['Close'].iloc[-1]
            vix_val = float(vix.iloc[0]) if hasattr(vix, "iloc") else float(vix)
            if vix_val > self.vix_threshold:
                logger.critical(f"BLACK SWAN ALERT! VIX = {vix_val:.2f}. Suspending new trades.")
                return True
        except Exception as e:
            logger.warning(f"Failed to check VIX: {e}")
        return False

    def is_flash_crash(self, ltf_df: pd.DataFrame) -> bool:
        """Checks if current price deviated abnormally (4+ std dev) from recent mean."""
        if ltf_df is None or len(ltf_df) < 50:
            return False

        try:
            closes = ltf_df['Close']
            mean = closes.rolling(window=50).mean().iloc[-1]
            std = closes.rolling(window=50).std().iloc[-1]
            current = closes.iloc[-1]

            if std == 0: return False

            z_score = (current - mean) / std
            if abs(z_score) >= self.z_score_threshold:
                logger.critical(f"FLASH CRASH DETECTED! Z-Score = {z_score:.2f}")
                return True
        except Exception as e:
            logger.warning(f"Z-Score calculation failed: {e}")

        return False

    async def fetch_macro_data(self):
        """Fetches DXY and 10Y Yields for regime filter."""
        try:
            dxy = yf.download("DX-Y.NYB", period="100d", progress=False)
            tnx = yf.download("^TNX", period="100d", progress=False)
            self.macro_data = {"DXY": dxy, "TNX": tnx}
        except Exception as e:
            logger.warning(f"Failed to fetch macro data: {e}")

    def get_regime_veto(self, direction: str, category: str) -> bool:
        """Vetos LONGs in Metals/EM if DXY and Yields are strongly rising."""
        if category not in ["METALS", "FOREX", "AGRI"]:
            return False

        dxy = self.macro_data.get("DXY")
        tnx = self.macro_data.get("TNX")

        if dxy is None or tnx is None or dxy.empty or tnx.empty:
            return False

        try:
            dxy_close = float(dxy['Close'].iloc[-1].iloc[0] if hasattr(dxy['Close'].iloc[-1], "iloc") else dxy['Close'].iloc[-1])
            dxy_sma = float(dxy['Close'].rolling(50).mean().iloc[-1].iloc[0] if hasattr(dxy['Close'].rolling(50).mean().iloc[-1], "iloc") else dxy['Close'].rolling(50).mean().iloc[-1])

            tnx_close = float(tnx['Close'].iloc[-1].iloc[0] if hasattr(tnx['Close'].iloc[-1], "iloc") else tnx['Close'].iloc[-1])
            tnx_sma = float(tnx['Close'].rolling(50).mean().iloc[-1].iloc[0] if hasattr(tnx['Close'].rolling(50).mean().iloc[-1], "iloc") else tnx['Close'].rolling(50).mean().iloc[-1])

            dxy_uptrend = dxy_close > dxy_sma
            tnx_uptrend = tnx_close > tnx_sma

            if dxy_uptrend and tnx_uptrend and direction == "LONG":
                logger.warning(f"Macro Veto! DXY and TNX rising. Rejecting {category} LONG.")
                return True
        except Exception as e:
            logger.warning(f"Regime veto calculation failed: {e}")

        return False
