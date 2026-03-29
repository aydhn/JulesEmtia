import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from ed_quant_engine.core.logger import logger
from ed_quant_engine.notifications.notifier import send_telegram_message

def get_macro_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Fetches macroeconomic indicators (DXY, TNX, VIX).
    Provides Regime and Black Swan (VIX Circuit Breaker) detection.
    """
    try:
        # 1. DXY (US Dollar Index)
        dxy = yf.download("DX-Y.NYB", period="1y", interval="1d", progress=False)
        # 2. US 10-Year Yield
        tnx = yf.download("^TNX", period="1y", interval="1d", progress=False)
        # 3. VIX (Volatility Index)
        vix = yf.download("^VIX", period="1y", interval="1d", progress=False)

        # Clean MultiIndex columns
        for df in [dxy, tnx, vix]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = df.index.tz_convert(None)
            df.ffill(inplace=True)
            df.bfill(inplace=True)

        return dxy, tnx, vix
    except Exception as e:
        logger.error(f"Macro Filter Data Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def check_vix_circuit_breaker(vix_df: pd.DataFrame, threshold: float = 30.0) -> bool:
    """
    If VIX is above 30 or spiked > 20% in a day, halt trading! (Black Swan Protection)
    Returns True if Circuit Breaker is active.
    """
    if vix_df.empty:
        return False

    current_vix = vix_df['Close'].iloc[-1]
    prev_vix = vix_df['Close'].iloc[-2]
    spike_pct = (current_vix - prev_vix) / prev_vix

    if current_vix >= threshold or spike_pct > 0.20:
        msg = f"🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi! Sistem Savunma Moduna Geçti. VIX: {current_vix:.2f} (Spike: {spike_pct*100:.1f}%)"
        logger.critical(msg)
        send_telegram_message(msg, force=True)
        return True

    return False

def determine_regime(dxy_df: pd.DataFrame, tnx_df: pd.DataFrame) -> str:
    """
    Identifies Risk-On / Risk-Off environments to Veto Long signals in Metals/Softs.
    """
    if dxy_df.empty or tnx_df.empty:
        return "Neutral"

    # Calculate 50-day moving averages
    dxy_sma50 = dxy_df['Close'].rolling(window=50).mean().iloc[-1]
    dxy_close = dxy_df['Close'].iloc[-1]

    tnx_sma50 = tnx_df['Close'].rolling(window=50).mean().iloc[-1]
    tnx_close = tnx_df['Close'].iloc[-1]

    if dxy_close > dxy_sma50 and tnx_close > tnx_sma50:
        return "Risk-Off" # Dollar up, Yields up (Bad for risk assets like Gold/Equities)
    elif dxy_close < dxy_sma50 and tnx_close < tnx_sma50:
        return "Risk-On" # Dollar down, Yields down (Good for Gold/Risk assets)
    else:
        return "Neutral"

def get_benchmark_return(start_date: str) -> float:
    """
    Benchmark calculation: Buy & Hold USD/TRY since the start.
    """
    try:
        usdtry = yf.download("USDTRY=X", start=start_date, progress=False)
        if usdtry.empty: return 0.0

        if isinstance(usdtry.columns, pd.MultiIndex):
            usdtry.columns = usdtry.columns.get_level_values(0)

        start_price = usdtry['Close'].iloc[0]
        end_price = usdtry['Close'].iloc[-1]

        return (end_price - start_price) / start_price * 100
    except Exception as e:
        logger.error(f"Benchmark Error: {e}")
        return 0.0
