import numpy as np
from src.config import VIX_THRESHOLD, Z_SCORE_THRESHOLD
from src.logger import get_logger

logger = get_logger()

def check_circuit_breaker(macro_data: dict) -> bool:
    """
    Returns True if a VIX Black Swan event is detected, meaning no new trades should be opened.
    """
    vix = macro_data.get("VIX", 0.0)
    if vix > VIX_THRESHOLD:
        logger.warning(f"🚨 CIRCUIT BREAKER TRIGGERED! VIX is {vix:.2f} > {VIX_THRESHOLD}. Halting new entries.")
        return True
    return False

def check_flash_crash(df, z_threshold=Z_SCORE_THRESHOLD) -> bool:
    """
    Checks for sudden price anomalies using rolling Z-Score.
    Returns True if an anomaly is detected.
    """
    if len(df) < 50:
        return False

    mean = df['Close'].rolling(window=50).mean().iloc[-1]
    std = df['Close'].rolling(window=50).std().iloc[-1]
    current_price = df['Close'].iloc[-1]

    if std > 0:
        z_score = (current_price - mean) / std
        if abs(z_score) > z_threshold:
            logger.warning(f"🚨 FLASH CRASH DETECTED! Z-Score: {z_score:.2f}")
            return True
    return False

def check_macro_regime_veto(ticker: str, direction: str, macro_data: dict) -> bool:
    """
    Rejects Long positions on Metals and TRY Forex if the regime is Risk-Off (strong DXY/US10Y).
    Returns False if vetoed (do not trade), True if approved.
    """
    from src.config import UNIVERSE

    regime = macro_data.get("Regime", "Risk-On")

    if regime == "Risk-Off" and direction == "Long":
        if ticker in UNIVERSE.get("Metals", []) or ticker in UNIVERSE.get("Forex_TRY", []):
            logger.info(f"Macro Regime Veto: Rejected Long on {ticker} due to Risk-Off regime.")
            return False

    return True
