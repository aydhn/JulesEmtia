import yfinance as yf
import pandas as pd
from utils.logger import log

def get_vix_data() -> pd.DataFrame:
    df = yf.download("^VIX", period="5d", progress=False)
    if df.empty or len(df) < 2: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df

def check_vix_circuit_breaker() -> bool:
    try:
        vix = get_vix_data()
        if vix.empty: return False

        latest_vix = vix['Close'].iloc[-1].item() if hasattr(vix['Close'].iloc[-1], 'item') else float(vix['Close'].iloc[-1])
        prev_vix = vix['Close'].iloc[-2].item() if hasattr(vix['Close'].iloc[-2], 'item') else float(vix['Close'].iloc[-2])

        if latest_vix > 30.0 or (latest_vix - prev_vix) / prev_vix > 0.20:
            log.critical(f"🚨 VIX DEVRE KESİCİ AKTİF! VIX: {latest_vix:.2f} (Önceki: {prev_vix:.2f})")
            return True

    except Exception as e:
        log.error(f"VIX kontrol hatası: {e}")
    return False

def get_macro_data(ticker: str) -> pd.DataFrame:
    df = yf.download(ticker, period="60d", progress=False)
    if df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    return df['Close']

def get_macro_regime() -> str:
    try:
        dxy = get_macro_data("DX-Y.NYB")
        tnx = get_macro_data("^TNX")

        if dxy.empty or tnx.empty or len(dxy) < 50 or len(tnx) < 50:
            return "RISK_ON"

        latest_dxy = dxy.iloc[-1].item() if hasattr(dxy.iloc[-1], 'item') else float(dxy.iloc[-1])
        ma_50_dxy = dxy.rolling(50).mean().iloc[-1].item() if hasattr(dxy.rolling(50).mean().iloc[-1], 'item') else float(dxy.rolling(50).mean().iloc[-1])

        latest_tnx = tnx.iloc[-1].item() if hasattr(tnx.iloc[-1], 'item') else float(tnx.iloc[-1])
        ma_50_tnx = tnx.rolling(50).mean().iloc[-1].item() if hasattr(tnx.rolling(50).mean().iloc[-1], 'item') else float(tnx.rolling(50).mean().iloc[-1])

        if latest_dxy > ma_50_dxy and latest_tnx > ma_50_tnx:
            log.info(f"Makro Rejim: RISK_OFF (DXY: {latest_dxy:.2f} > {ma_50_dxy:.2f}, TNX: {latest_tnx:.2f} > {ma_50_tnx:.2f})")
            return "RISK_OFF"

    except Exception as e:
        log.error(f"Macro regime kontrol hatası: {e}")

    return "RISK_ON"
