import yfinance as yf
import pandas as pd
from data.data_loader import exponential_backoff

class MacroFilter:
    def __init__(self):
        pass

    @exponential_backoff
    def get_macro_regime(self) -> dict:
        vix = yf.download("^VIX", period="5d", progress=False)
        dxy = yf.download("DX-Y.NYB", period="5d", progress=False)
        us10y = yf.download("^TNX", period="5d", progress=False)

        if vix.empty or dxy.empty or us10y.empty:
            return {"VIX": 0, "Black_Swan": False, "DXY_Trend": 0, "US10Y_Trend": 0}

        vix_val = float(vix['Close'].iloc[-1])
        is_black_swan = vix_val > 35.0

        dxy_trend = 1 if float(dxy['Close'].iloc[-1]) > float(dxy['Close'].iloc[-5]) else -1
        us10y_trend = 1 if float(us10y['Close'].iloc[-1]) > float(us10y['Close'].iloc[-5]) else -1

        return {
            "VIX": vix_val,
            "Black_Swan": is_black_swan,
            "DXY_Trend": dxy_trend,
            "US10Y_Trend": us10y_trend
        }
