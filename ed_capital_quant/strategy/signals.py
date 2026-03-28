import pandas as pd
from data.macro_filter import check_vix_circuit_breaker, get_macro_regime
from data.sentiment import get_news_sentiment

def generate_signals(df: pd.DataFrame, ticker: str) -> int:
    if check_vix_circuit_breaker():
        return 0

    sentiment_score = get_news_sentiment(ticker.split('=')[0])
    if get_macro_regime() == "RISK_OFF" and sentiment_score < -0.5:
        return 0

    close = df['Close'].iloc[-2]
    ema_50 = df['EMA_50'].iloc[-2]
    rsi = df['RSI_14'].iloc[-2]
    macd = df['MACDh_12_26_9'].iloc[-2]
    bb_lower = df['BBL_20_2.0'].iloc[-2]
    bb_upper = df['BBU_20_2.0'].iloc[-2]

    if close > ema_50 and (rsi < 30 or close <= bb_lower) and macd > 0:
        return 1
    elif close < ema_50 and (rsi > 70 or close >= bb_upper) and macd < 0:
        return -1
    return 0

def calc_dynamic_sl_tp(entry_price: float, atr: float, direction: int):
    if direction == 1:
        sl = entry_price - (1.5 * atr)
        tp = entry_price + (3.0 * atr)
    else:
        sl = entry_price + (1.5 * atr)
        tp = entry_price - (3.0 * atr)
    return sl, tp
