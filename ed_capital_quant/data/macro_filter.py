import yfinance as yf
from utils.logger import log

def check_vix_circuit_breaker() -> bool:
    try:
        vix = yf.download("^VIX", period="5d", progress=False)
        if vix.empty or len(vix) < 2: return False
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [c[0] for c in vix.columns]
        latest_vix = vix['Close'].iloc[-1].item() if hasattr(vix['Close'].iloc[-1], 'item') else float(vix['Close'].iloc[-1])
        prev_vix = vix['Close'].iloc[-2].item() if hasattr(vix['Close'].iloc[-2], 'item') else float(vix['Close'].iloc[-2])

        if latest_vix > 30.0 or (latest_vix - prev_vix) / prev_vix > 0.20:
            log.critical(f"🚨 VIX DEVRE KESİCİ AKTİF! VIX: {latest_vix}")
            return True
    except Exception as e:
        log.error(f"VIX kontrol hatası: {e}")
    return False

def get_macro_regime() -> str:
    try:
        dxy = yf.download("DX-Y.NYB", period="60d", progress=False)
        if dxy.empty: return "RISK_ON"
        if isinstance(dxy.columns, pd.MultiIndex):
            dxy.columns = [c[0] for c in dxy.columns]
        dxy = dxy['Close']
        if len(dxy) < 50: return "RISK_ON"
        latest_dxy = dxy.iloc[-1].item() if hasattr(dxy.iloc[-1], 'item') else float(dxy.iloc[-1])
        ma_50 = dxy.rolling(50).mean().iloc[-1].item() if hasattr(dxy.rolling(50).mean().iloc[-1], 'item') else float(dxy.rolling(50).mean().iloc[-1])
        if latest_dxy > ma_50:
            return "RISK_OFF"
    except Exception as e:
        log.error(f"Macro regime kontrol hatası: {e}")
    return "RISK_ON"
