import pandas as pd
import yfinance as yf
from config import TICKERS, VIX_CIRCUIT_BREAKER_THRESHOLD
from logger import log

def get_macro_data() -> dict:
    """Fetches key macroeconomic indicators from Yahoo Finance."""
    macro_data = {}
    for ticker in TICKERS["MACRO"]:
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.ffill(inplace=True)
            macro_data[ticker] = df
        except Exception as e:
            log.error(f"Failed to fetch macro data for {ticker}: {e}")
    return macro_data

def check_vix_circuit_breaker() -> bool:
    """Checks if the VIX is above the critical threshold (Black Swan mode)."""
    try:
        df = yf.download("^VIX", period="5d", interval="1d", progress=False)
        if df.empty:
            return False
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        last_vix = df['Close'].iloc[-1]

        if last_vix > VIX_CIRCUIT_BREAKER_THRESHOLD:
            log.critical(f"🚨 VIX CIRCUIT BREAKER ACTIVATED: {last_vix:.2f} > {VIX_CIRCUIT_BREAKER_THRESHOLD}")
            return True
        return False
    except Exception as e:
        log.error(f"Error checking VIX: {e}")
        return False

def check_macro_regime(ticker: str) -> str:
    """
    Returns the market regime: 'RISK_ON', 'RISK_OFF', or 'NEUTRAL'.
    Uses DXY and US10Y yields.
    """
    macro = get_macro_data()
    if "DX-Y.NYB" not in macro or "^TNX" not in macro:
        return "NEUTRAL"

    dxy = macro["DX-Y.NYB"]
    tnx = macro["^TNX"]

    # Calculate simple 50-day SMA trend
    dxy_sma50 = dxy['Close'].rolling(50).mean().iloc[-1]
    dxy_close = dxy['Close'].iloc[-1]

    tnx_sma50 = tnx['Close'].rolling(50).mean().iloc[-1]
    tnx_close = tnx['Close'].iloc[-1]

    # Risk-Off Definition: Strong Dollar AND Rising Yields
    if dxy_close > dxy_sma50 and tnx_close > tnx_sma50:
        return "RISK_OFF"

    # Risk-On Definition: Weak Dollar AND Falling Yields
    elif dxy_close < dxy_sma50 and tnx_close < tnx_sma50:
        return "RISK_ON"

    return "NEUTRAL"
