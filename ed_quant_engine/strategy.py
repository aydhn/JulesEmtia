import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from ed_quant_engine.logger import log
from ed_quant_engine.config import (
    RSI_OVERBOUGHT, RSI_OVERSOLD, SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER,
    INITIAL_CAPITAL, MAX_RISK_PER_TRADE
)
from ed_quant_engine.execution_model import simulate_execution

def generate_signals(df_mtf: pd.DataFrame, ticker: str, current_capital: float, risk_fraction: float = MAX_RISK_PER_TRADE) -> Optional[Dict[str, Any]]:
    """Generates signals based on MTF confluence, Risk/Reward, and Position Sizing."""

    if df_mtf is None or df_mtf.empty:
        return None

    latest = df_mtf.iloc[-1]

    # 1. HTF (Daily) Trend Filter: Must be aligned
    htf_close = latest['HTF_Close']
    htf_ema50 = latest['HTF_EMA_50']
    htf_macd = latest['HTF_MACD_12_26_9']

    htf_trend_up = (htf_close > htf_ema50) and (htf_macd > 0)
    htf_trend_down = (htf_close < htf_ema50) and (htf_macd < 0)

    if not (htf_trend_up or htf_trend_down):
        log.debug(f"[{ticker}] No clear daily trend. Flat market.")
        return None

    # 2. LTF (Hourly) Entry Triggers: RSI Reversion or BB Bounce
    ltf_close = latest['Close']
    ltf_rsi = latest['RSI_14']
    ltf_bb_lower = latest['BBL_5_2.0']
    ltf_bb_upper = latest['BBU_5_2.0']

    ltf_macd_hist = latest['MACDh_12_26_9']

    # Signal Conditions
    long_signal = htf_trend_up and (
        (ltf_rsi < RSI_OVERSOLD or ltf_close <= ltf_bb_lower) and
        (ltf_macd_hist > 0) # MACD histogram turned positive
    )

    short_signal = htf_trend_down and (
        (ltf_rsi > RSI_OVERBOUGHT or ltf_close >= ltf_bb_upper) and
        (ltf_macd_hist < 0) # MACD histogram turned negative
    )

    direction = None
    if long_signal:
        direction = 'Long'
    elif short_signal:
        direction = 'Short'

    if not direction:
        return None

    # 3. Dynamic Risk Management (JP Morgan Style)
    current_atr = latest['ATRr_14']
    atr_sma = df_mtf['ATRr_14'].tail(50).mean() # For execution model

    # Simulate execution price with slippage and spread
    entry_price = simulate_execution(ticker, direction, ltf_close, current_atr, atr_sma)

    if direction == 'Long':
        sl_price = entry_price - (current_atr * SL_ATR_MULTIPLIER)
        tp_price = entry_price + (current_atr * TP_ATR_MULTIPLIER)
        sl_distance = entry_price - sl_price
    else: # Short
        sl_price = entry_price + (current_atr * SL_ATR_MULTIPLIER)
        tp_price = entry_price - (current_atr * TP_ATR_MULTIPLIER)
        sl_distance = sl_price - entry_price

    # 4. Position Sizing (Fractional Kelly Integration)
    risk_amount = current_capital * risk_fraction

    if sl_distance <= 0:
        log.error(f"[{ticker}] Invalid SL distance {sl_distance:.4f}. ATR: {current_atr:.4f}")
        return None

    position_size = risk_amount / sl_distance

    # Convert to percentage of portfolio for universal tracking
    position_size_pct = (position_size * entry_price) / current_capital * 100.0

    log.info(f"[{ticker}] {direction} SIGNAL GENERATED. Entry: {entry_price:.4f}, SL: {sl_price:.4f}, Risk%: {risk_fraction:.2%}")

    return {
        "ticker": ticker,
        "direction": direction,
        "entry_price": entry_price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "position_size": position_size_pct,
        "atr": current_atr,
        "atr_sma": atr_sma
    }

if __name__ == "__main__":
    from ed_quant_engine.features import add_features, align_mtf_data
    from ed_quant_engine.data_loader import fetch_data

    df_1d = fetch_data("GC=F", "1d")
    df_1h = fetch_data("GC=F", "1h")

    if df_1d is not None and df_1h is not None:
        df_1d_feat = add_features(df_1d)
        df_1h_feat = add_features(df_1h)
        df_mtf = align_mtf_data(df_1d_feat, df_1h_feat)

        signal = generate_signals(df_mtf, "GC=F", 10000.0)
        print("Signal:", signal)
