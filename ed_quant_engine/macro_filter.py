import yfinance as yf
import pandas as pd
import numpy as np
from logger import get_logger

log = get_logger()

def check_vix_circuit_breaker(vix_threshold: float = 35.0, jump_pct: float = 0.20) -> bool:
    """
    Checks if S&P 500 VIX index implies a 'Black Swan' or panic regime.
    Returns True if Circuit Breaker is triggered (HALT ALL NEW TRADES).
    """
    try:
        vix = yf.download("^VIX", period="5d", interval="1d", progress=False)['Close']
        if vix.empty: return False

        # Flatten MultiIndex if yfinance returns one
        if isinstance(vix, pd.DataFrame):
            current_vix = float(vix.iloc[-1, 0])
            prev_vix = float(vix.iloc[-2, 0])
        else:
            current_vix = float(vix.iloc[-1])
            prev_vix = float(vix.iloc[-2])

        pct_change = (current_vix - prev_vix) / prev_vix

        if current_vix >= vix_threshold or pct_change >= jump_pct:
            log.critical(f"🚨 VIX CIRCUIT BREAKER TRIGGERED: VIX @ {current_vix:.2f} (Jump: {pct_change*100:.1f}%)")
            return True

        return False
    except Exception as e:
        log.error(f"Error fetching VIX: {e}")
        return False

def check_zscore_flash_crash(df: pd.DataFrame, window: int = 50, z_thresh: float = 4.0) -> bool:
    """
    Calculates rolling Z-Score. If the latest close is > 4 std deviations away,
    it indicates an anomaly/flash crash. Return True if crash detected.
    """
    close_col = [c for c in df.columns if c[0] == 'Close'][0] if isinstance(df.columns, pd.MultiIndex) else 'Close'
    closes = df[close_col]

    rolling_mean = closes.rolling(window=window).mean()
    rolling_std = closes.rolling(window=window).std()

    z_scores = (closes - rolling_mean) / rolling_std
    latest_z = abs(float(z_scores.iloc[-1]))

    if latest_z >= z_thresh:
        log.warning(f"Z-Score Anomaly Detected: {latest_z:.2f} standard deviations. Halting ticker.")
        return True
    return False

def get_macro_regime() -> str:
    """
    Fetches DXY and TNX to determine market regime.
    Risk-On: DXY down, Yields down.
    Risk-Off: DXY up, Yields up (Strong Dollar/Squeeze).
    """
    try:
        dxy = yf.download("DX-Y.NYB", period="60d", interval="1d", progress=False)['Close']
        tnx = yf.download("^TNX", period="60d", interval="1d", progress=False)['Close']

        # Simple Logic: Is DXY above 50-day SMA?
        # Flatten MultiIndex
        dxy_val = float(dxy.iloc[-1, 0]) if isinstance(dxy, pd.DataFrame) else float(dxy.iloc[-1])
        dxy_sma50 = float(dxy.mean().iloc[0]) if isinstance(dxy, pd.DataFrame) else float(dxy.mean())

        if dxy_val > dxy_sma50:
            return "Risk-Off"
        return "Risk-On"
    except Exception as e:
        log.error(f"Error fetching Macro Regime: {e}")
        return "Neutral"
