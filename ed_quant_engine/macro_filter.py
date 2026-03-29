import yfinance as yf
import pandas as pd
import numpy as np
import time
from ed_quant_engine.logger import log
from ed_quant_engine.config import VIX_CRITICAL_LEVEL, Z_SCORE_FLASH_CRASH

def fetch_macro_data() -> pd.DataFrame:
    """Fetches DXY, US 10Y Yield, and VIX to determine Market Regime and Black Swan events."""
    tickers = ["DX-Y.NYB", "^TNX", "^VIX"]
    df = yf.download(tickers, period="1mo", interval="1d", progress=False)

    if df.empty:
        log.warning("Failed to fetch macro data. Returning empty DataFrame.")
        return pd.DataFrame()

    df = df['Close']
    df.ffill(inplace=True)
    df.dropna(inplace=True)
    return df

def detect_black_swan(macro_df: pd.DataFrame) -> bool:
    """Returns True if VIX is above the critical threshold or spiked >20% today."""
    if macro_df.empty or "^VIX" not in macro_df.columns:
        return False

    latest_vix = macro_df["^VIX"].iloc[-1]
    prev_vix = macro_df["^VIX"].iloc[-2] if len(macro_df) > 1 else latest_vix

    spike_pct = (latest_vix - prev_vix) / prev_vix

    if latest_vix >= VIX_CRITICAL_LEVEL:
        log.critical(f"BLACK SWAN DETECTED: VIX @ {latest_vix:.2f} >= {VIX_CRITICAL_LEVEL}!")
        return True
    elif spike_pct >= 0.20:
        log.critical(f"BLACK SWAN DETECTED: VIX spiked {spike_pct*100:.1f}% today!")
        return True

    return False

def get_market_regime(macro_df: pd.DataFrame) -> str:
    """Determines Risk-On or Risk-Off regime based on DXY and Yield momentum."""
    if macro_df.empty or "DX-Y.NYB" not in macro_df.columns or "^TNX" not in macro_df.columns:
        return "Neutral"

    dxy_sma10 = macro_df["DX-Y.NYB"].rolling(10).mean().iloc[-1]
    tnx_sma10 = macro_df["^TNX"].rolling(10).mean().iloc[-1]

    latest_dxy = macro_df["DX-Y.NYB"].iloc[-1]
    latest_tnx = macro_df["^TNX"].iloc[-1]

    if latest_dxy > dxy_sma10 and latest_tnx > tnx_sma10:
        return "Risk-Off" # Strong dollar, high yields = bad for metals/emerging
    elif latest_dxy < dxy_sma10 and latest_tnx < tnx_sma10:
        return "Risk-On" # Weak dollar, low yields = good for risk assets
    else:
        return "Neutral"

def detect_flash_crash(df: pd.DataFrame, window: int = 20) -> bool:
    """Calculates Z-Score of the latest close to detect micro-anomalies (Flash Crashes)."""
    if len(df) < window:
        return False

    closes = df['Close'].tail(window)
    mean = closes.mean()
    std = closes.std()

    if std == 0: return False

    latest_close = closes.iloc[-1]
    z_score = (latest_close - mean) / std

    if abs(z_score) >= Z_SCORE_FLASH_CRASH:
        log.critical(f"FLASH CRASH ANOMALY: Z-Score = {z_score:.2f} (Threshold: {Z_SCORE_FLASH_CRASH})")
        return True

    return False

if __name__ == "__main__":
    df = fetch_macro_data()
    print("Market Regime:", get_market_regime(df))
    print("Black Swan:", detect_black_swan(df))
