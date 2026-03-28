import pandas as pd
from data.macro_filter import check_vix_circuit_breaker, get_macro_regime
from data.sentiment import get_news_sentiment

def generate_signals(df: pd.DataFrame, ticker: str) -> int:
    # Phase 19: VIX Veto
    if check_vix_circuit_breaker():
        return 0

    # Phase 6 & Phase 20: Macro and Sentiment Veto
    sentiment_score = get_news_sentiment(ticker.split('=')[0])
    macro_regime = get_macro_regime()

    # Do not execute if macro tells us to risk off and sentiment is negative
    if macro_regime == "RISK_OFF" and sentiment_score < -0.5:
        return 0

    # Shift(-1) on signals is done by checking iloc[-1] (the last closed candle, because in `main.py` we run at H:01 and df iloc[-1] is the *previous* hour's closed candle)
    # However, to be extra safe in backtesting/realtime, we always look at the PREVIOUS row for the signal.
    idx = -2 if len(df) > 1 else -1

    close_ltf = df['Close'].iloc[idx]
    ema_50_ltf = df['EMA_50'].iloc[idx]
    rsi_ltf = df['RSI_14'].iloc[idx]
    macd_ltf = df['MACDh_12_26_9'].iloc[idx]
    bb_lower_ltf = df['BBL_20_2.0'].iloc[idx]
    bb_upper_ltf = df['BBU_20_2.0'].iloc[idx]

    # HTF checks (if available)
    if 'Close_HTF' in df.columns:
        close_htf = df['Close_HTF'].iloc[idx]
        ema_50_htf = df['EMA_50_HTF'].iloc[idx]
        macd_htf = df['MACDh_12_26_9_HTF'].iloc[idx]
    else:
        # Fallback to LTF if HTF not available
        close_htf = close_ltf
        ema_50_htf = ema_50_ltf
        macd_htf = macd_ltf

    # LONG Conditions
    htf_long_ok = (close_htf > ema_50_htf) and (macd_htf > 0)
    ltf_long_ok = (rsi_ltf < 30 or close_ltf <= bb_lower_ltf) and (close_ltf > ema_50_ltf)

    if htf_long_ok and ltf_long_ok:
        return 1

    # SHORT Conditions
    htf_short_ok = (close_htf < ema_50_htf) and (macd_htf < 0)
    ltf_short_ok = (rsi_ltf > 70 or close_ltf >= bb_upper_ltf) and (close_ltf < ema_50_ltf)

    if htf_short_ok and ltf_short_ok:
        return -1

    return 0

def calc_dynamic_sl_tp(entry_price: float, atr: float, direction: int):
    # Phase 4: Dynamic ATR-based Risk Management
    # SL = 1.5 ATR, TP = 3.0 ATR (1:2 R:R)
    if direction == 1:
        sl = entry_price - (1.5 * atr)
        tp = entry_price + (3.0 * atr)
    else:
        sl = entry_price + (1.5 * atr)
        tp = entry_price - (3.0 * atr)
    return sl, tp
