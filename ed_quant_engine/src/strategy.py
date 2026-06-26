from __future__ import annotations

from typing import Any

import pandas as pd

from src.config import MAX_SINGLE_RISK_CAP, get_spread
from src.logger import get_logger
from src.portfolio import calculate_fractional_kelly


logger = get_logger()


def _first_col(df: pd.DataFrame, prefix: str) -> str | None:
    cols = [c for c in df.columns if c.startswith(prefix)]
    return cols[0] if cols else None


def _value(row: pd.Series, key: str | None, default: float = 0.0) -> float:
    if not key:
        return default
    val = row.get(key, default)
    if pd.isna(val):
        return default
    return float(val)


def generate_signals(
    df: pd.DataFrame,
    ticker: str,
    current_balance: float,
    macro_regime: str = "Risk-On",
) -> dict[str, Any] | None:
    """
    Builds a confluence signal from the last closed candle and prices entry on
    the current candle. No active candle indicator is used for confirmation.
    """
    required = {"Close", "High", "Low", "EMA_50", "EMA_200", "RSI_14", "ATR_14"}
    if df.empty or len(df) < 3 or not required.issubset(df.columns):
        return None

    last = df.iloc[-2]
    prev = df.iloc[-3]
    current = df.iloc[-1]
    current_price = float(current["Close"])

    atr_raw = _value(last, "ATR_14", current_price * 0.01)
    atr = atr_raw if atr_raw >= current_price * 0.001 else current_price * 0.005

    macd_col = _first_col(df, "MACDh")
    adx_col = _first_col(df, "ADX_")
    stoch_k_col = _first_col(df, "STOCHRSIk")
    stoch_d_col = _first_col(df, "STOCHRSId")
    bb_lower_col = _first_col(df, "BBL_")
    bb_upper_col = _first_col(df, "BBU_")
    supertrend_dir_col = _first_col(df, "SUPERTd_")
    keltner_lower_col = _first_col(df, "KCL_") or ("KELTNER_LOWER_20" if "KELTNER_LOWER_20" in df.columns else None)
    keltner_upper_col = _first_col(df, "KCU_") or ("KELTNER_UPPER_20" if "KELTNER_UPPER_20" in df.columns else None)

    macd = _value(last, macd_col)
    macd_prev = _value(prev, macd_col)
    adx = _value(last, adx_col)
    stoch_k = _value(last, stoch_k_col, 50)
    stoch_d = _value(last, stoch_d_col, 50)
    bb_lower = _value(last, bb_lower_col)
    bb_upper = _value(last, bb_upper_col)
    kc_lower = _value(last, keltner_lower_col)
    kc_upper = _value(last, keltner_upper_col)
    supertrend_dir = _value(last, supertrend_dir_col)
    cmf = _value(last, "CMF_20")
    mfi = _value(last, "MFI_14", 50)
    vol_regime = _value(last, "VOL_REGIME")

    htf_close = _value(last, "HTF_Close")
    htf_ema50 = _value(last, "HTF_EMA_50")
    htf_ema200 = _value(last, "HTF_EMA_200")
    htf_trend_up = htf_close > htf_ema50 > 0 and (htf_ema50 >= htf_ema200 or htf_ema200 == 0)
    htf_trend_down = htf_close < htf_ema50 if htf_ema50 else True
    if not htf_close:
        htf_trend_up = True
        htf_trend_down = True

    trend_up = last["Close"] > last["EMA_50"] > last["EMA_200"]
    trend_down = last["Close"] < last["EMA_50"] < last["EMA_200"]
    macd_cross_up = macd > 0 or (macd_prev < 0 < macd)
    macd_cross_down = macd < 0 or (macd_prev > 0 > macd)
    bb_reversal_long = bb_lower > 0 and prev["Low"] <= bb_lower and last["Close"] > bb_lower
    bb_reversal_short = bb_upper > 0 and prev["High"] >= bb_upper and last["Close"] < bb_upper
    channel_break_long = last["Close"] > max(_value(last, "DONCHIAN_HIGH_20"), kc_upper)
    channel_break_short = last["Close"] < min(_value(last, "DONCHIAN_LOW_20", float("inf")), kc_lower or float("inf"))

    trend_long = trend_up and htf_trend_up and adx >= 22 and macd_cross_up and cmf >= -0.05
    trend_short = trend_down and htf_trend_down and adx >= 22 and macd_cross_down and cmf <= 0.05

    div_long = (
        (last.get("Bull_Div", 0) == 1 or last.get("MACD_Bull_Div", 0) == 1 or last.get("MFI_Bull_Div", 0) == 1)
        and stoch_k < 35
        and stoch_k >= stoch_d
        and mfi < 45
        and htf_trend_up
    )
    div_short = (
        (last.get("Bear_Div", 0) == 1 or last.get("MACD_Bear_Div", 0) == 1 or last.get("MFI_Bear_Div", 0) == 1)
        and stoch_k > 65
        and stoch_k <= stoch_d
        and mfi > 55
        and htf_trend_down
    )

    momentum_long = channel_break_long and last["RSI_14"] > 58 and macd > 0 and supertrend_dir >= 0
    momentum_short = channel_break_short and last["RSI_14"] < 42 and macd < 0 and supertrend_dir <= 0
    mean_long = bb_reversal_long and last["RSI_14"] < 45 and mfi < 45 and cmf > -0.20
    mean_short = bb_reversal_short and last["RSI_14"] > 55 and mfi > 55 and cmf < 0.20

    is_long = trend_long or div_long or momentum_long or mean_long
    is_short = trend_short or div_short or momentum_short or mean_short
    if is_long == is_short:
        return None

    direction = "Long" if is_long else "Short"
    sl_mult = 1.25 if abs(vol_regime) == 1 else 1.5
    tp_mult = 2.75 if abs(vol_regime) == 1 else 3.0
    if direction == "Long":
        sl_price = current_price - (sl_mult * atr)
        tp_price = current_price + (tp_mult * atr)
    else:
        sl_price = current_price + (sl_mult * atr)
        tp_price = current_price - (tp_mult * atr)

    risk_pct = min(calculate_fractional_kelly(), MAX_SINGLE_RISK_CAP)
    risk_amount = current_balance * risk_pct
    sl_distance = abs(current_price - sl_price)
    position_size = risk_amount / sl_distance if sl_distance > 0 else 0.0
    if position_size <= 0:
        return None

    tag_parts = []
    if trend_long or trend_short:
        tag_parts.append("trend")
    if div_long or div_short:
        tag_parts.append("divergence")
    if momentum_long or momentum_short:
        tag_parts.append("breakout")
    if mean_long or mean_short:
        tag_parts.append("mean_reversion")

    return {
        "ticker": ticker,
        "direction": direction,
        "entry_price": current_price,
        "sl_price": float(sl_price),
        "tp_price": float(tp_price),
        "position_size": float(position_size),
        "risk_pct": float(risk_pct),
        "atr": float(atr),
        "strategy_tag": "+".join(tag_parts) or "confluence",
        "features": last.to_dict(),
        "macro_regime": macro_regime,
    }


def manage_open_positions(broker, df_dict: dict[str, pd.DataFrame], black_swan: bool = False) -> list[dict[str, Any]]:
    """
    Applies SL/TP, breakeven and monotonic ATR trailing. Returns close receipts.
    """
    receipts: list[dict[str, Any]] = []
    for trade in broker.get_open_positions():
        ticker = trade["ticker"]
        df = df_dict.get(ticker)
        if df is None or df.empty or "Close" not in df.columns:
            continue

        current_price = float(df["Close"].iloc[-1])
        trade_id = int(trade["trade_id"])
        direction = trade["direction"]
        entry_price = float(trade["entry_price"])
        sl_price = float(trade["sl_price"])
        tp_price = float(trade["tp_price"])
        is_breakeven = bool(trade.get("is_breakeven", 0))
        partial_taken = bool(trade.get("partial_taken", 0))

        atr_raw = float(df["ATR_14"].iloc[-2]) if "ATR_14" in df.columns and len(df) >= 2 else current_price * 0.01
        atr = atr_raw if atr_raw >= current_price * 0.001 else current_price * 0.005
        spread = get_spread(ticker)
        trailing_multiplier = 0.5 if black_swan else 1.5
        breakeven_trigger = 0.5 if black_swan else 1.0

        if direction == "Long":
            if current_price <= sl_price:
                receipts.append(broker.close_position(trade_id, current_price, spread=spread, atr=atr, exit_reason="SL"))
                continue
            if current_price >= tp_price:
                receipts.append(broker.close_position(trade_id, current_price, spread=spread, atr=atr, exit_reason="TP"))
                continue
            if not partial_taken and current_price >= entry_price + ((tp_price - entry_price) * 0.5):
                broker.modify_trailing_stop(trade_id, max(sl_price, entry_price), is_breakeven=True)
                try:
                    import src.paper_db as db
                    db.mark_partial_taken(trade_id)
                except Exception:
                    pass
            elif current_price >= entry_price + (breakeven_trigger * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info("Breakeven set for %s Long", ticker)
            elif is_breakeven or black_swan:
                new_sl = current_price - (trailing_multiplier * atr)
                if new_sl > sl_price:
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)

        elif direction == "Short":
            if current_price >= sl_price:
                receipts.append(broker.close_position(trade_id, current_price, spread=spread, atr=atr, exit_reason="SL"))
                continue
            if current_price <= tp_price:
                receipts.append(broker.close_position(trade_id, current_price, spread=spread, atr=atr, exit_reason="TP"))
                continue
            if not partial_taken and current_price <= entry_price - ((entry_price - tp_price) * 0.5):
                broker.modify_trailing_stop(trade_id, min(sl_price, entry_price), is_breakeven=True)
                try:
                    import src.paper_db as db
                    db.mark_partial_taken(trade_id)
                except Exception:
                    pass
            elif current_price <= entry_price - (breakeven_trigger * atr) and not is_breakeven:
                broker.modify_trailing_stop(trade_id, entry_price, is_breakeven=True)
                logger.info("Breakeven set for %s Short", ticker)
            elif is_breakeven or black_swan:
                new_sl = current_price + (trailing_multiplier * atr)
                if new_sl < sl_price:
                    broker.modify_trailing_stop(trade_id, new_sl, is_breakeven=True)

    return [r for r in receipts if r]
