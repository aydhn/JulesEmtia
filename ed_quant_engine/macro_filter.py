import yfinance as yf
import pandas as pd
import numpy as np
from typing import Optional

from logger import log

def fetch_macro_data() -> pd.DataFrame:
    """
    Fetches daily macroeconomic indicators (DXY & US10Y).
    These act as a global regime filter (Risk-On / Risk-Off).
    """
    try:
        # DX-Y.NYB = US Dollar Index, ^TNX = US 10-Year Treasury Yield
        tickers = ["DX-Y.NYB", "^TNX"]
        df = yf.download(tickers, period="1y", interval="1d", progress=False)["Close"]

        # Clean up column names in case of MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df.rename(columns={"DX-Y.NYB": "DXY", "^TNX": "US10Y"}, inplace=True)

        # Forward fill weekends/holidays
        df = df.ffill().dropna()

        # Calculate 50-day SMA for trend determination
        df["DXY_SMA50"] = df["DXY"].rolling(window=50).mean()
        df["US10Y_SMA50"] = df["US10Y"].rolling(window=50).mean()

        return df.dropna()

    except Exception as e:
        log.error(f"Failed to fetch macro data: {e}")
        return pd.DataFrame()


def get_market_regime() -> str:
    """
    Determines the current market regime based on DXY and US10Y trends.
    Risk-Off = Tightening (Strong USD, Rising Yields) -> Avoid Long Commodities/EM FX
    Risk-On = Loosening (Weak USD, Falling Yields)
    """
    df = fetch_macro_data()
    if df.empty:
        log.warning("Macro data empty. Defaulting to 'Neutral' regime.")
        return "Neutral"

    last_row = df.iloc[-1]

    # If DXY and Yields are both above their 50-day SMA, it's a strong Risk-Off environment.
    if last_row["DXY"] > last_row["DXY_SMA50"] and last_row["US10Y"] > last_row["US10Y_SMA50"]:
        return "Risk-Off"

    # If both are below, it's Risk-On.
    elif last_row["DXY"] < last_row["DXY_SMA50"] and last_row["US10Y"] < last_row["US10Y_SMA50"]:
        return "Risk-On"

    return "Neutral"


def is_black_swan_vix(threshold: float = 35.0) -> bool:
    """
    Monitors S&P 500 VIX (^VIX) for Black Swan / Extreme Panic events.
    If VIX is above threshold, NO new long trades are allowed.
    """
    try:
        df = yf.download("^VIX", period="5d", interval="1d", progress=False)["Close"]
        if df.empty:
            return False

        last_vix = df.iloc[-1].item() if isinstance(df.iloc[-1], pd.Series) else df.iloc[-1]

        if last_vix > threshold:
            log.critical(f"🚨 VIX CIRCUIT BREAKER ACTIVATED: {last_vix:.2f} > {threshold}")
            return True

        return False

    except Exception as e:
        log.error(f"VIX Check failed: {e}")
        return False


def is_flash_crash(df: pd.DataFrame, ticker: str, window: int = 50, z_threshold: float = 4.0) -> bool:
    """
    Micro Flash Crash detector using Z-Score Anomaly Detection on the LTF dataframe.
    Calculates if the current price is anomalously far from its moving average.
    """
    if len(df) < window:
        return False

    try:
        # Calculate Rolling Mean and Standard Deviation
        rolling_mean = df['close'].rolling(window=window).mean()
        rolling_std = df['close'].rolling(window=window).std()

        # Calculate Z-Score of the most recent closed candle
        current_price = df['close'].iloc[-1]
        mean_val = rolling_mean.iloc[-1]
        std_val = rolling_std.iloc[-1]

        if pd.isna(mean_val) or pd.isna(std_val) or std_val == 0:
            return False

        z_score = abs((current_price - mean_val) / std_val)

        if z_score > z_threshold:
            log.critical(f"🚨 FLASH CRASH ANOMALY on {ticker}: Z-Score {z_score:.2f} > {z_threshold}")
            return True

        return False

    except Exception as e:
        log.error(f"Flash crash detection failed for {ticker}: {e}")
        return False

