from __future__ import annotations

from src.config import UNIVERSE, VIX_THRESHOLD, Z_SCORE_THRESHOLD
from src.logger import get_logger


logger = get_logger()


def check_circuit_breaker(macro_data: dict) -> bool:
    vix = float(macro_data.get("VIX", 0.0) or 0.0)
    if vix > VIX_THRESHOLD:
        logger.warning("Circuit breaker triggered: VIX %.2f > %.2f. New entries halted.", vix, VIX_THRESHOLD)
        return True
    return False


def check_flash_crash(df, z_threshold=Z_SCORE_THRESHOLD) -> bool:
    if len(df) < 50:
        return False
    mean = df["Close"].rolling(window=50).mean().iloc[-1]
    std = df["Close"].rolling(window=50).std().iloc[-1]
    current_price = df["Close"].iloc[-1]
    if std > 0:
        z_score = (current_price - mean) / std
        if abs(z_score) > z_threshold:
            logger.warning("Flash-crash anomaly detected. Z-score %.2f", z_score)
            return True
    return False


def check_macro_regime_veto(ticker: str, direction: str, macro_data: dict) -> bool:
    regime = macro_data.get("Regime", "Risk-On")
    if regime == "Risk-Off" and direction == "Long":
        if ticker in UNIVERSE.get("Metals", []) or ticker in UNIVERSE.get("Forex_TRY", []):
            logger.info("Macro veto: rejected Long on %s due to Risk-Off regime.", ticker)
            return False
    return True
