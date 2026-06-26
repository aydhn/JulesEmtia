from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta


def _append_indicator(df: pd.DataFrame, indicator: pd.DataFrame | pd.Series | None) -> pd.DataFrame:
    if indicator is None:
        return df
    if isinstance(indicator, pd.Series):
        indicator = indicator.to_frame()
    out = pd.concat([df, indicator], axis=1)
    return out.loc[:, ~out.columns.duplicated()]


def _manual_mfi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    money_flow = typical * df["Volume"].replace(0, np.nan)
    direction = typical.diff()
    positive = money_flow.where(direction > 0, 0.0).rolling(length).sum()
    negative = money_flow.where(direction < 0, 0.0).abs().rolling(length).sum()
    ratio = positive / negative.replace(0, np.nan)
    return (100 - (100 / (1 + ratio))).rename("MFI_14")


def _manual_cmf(df: pd.DataFrame, length: int = 20) -> pd.Series:
    high_low = (df["High"] - df["Low"]).replace(0, np.nan)
    multiplier = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / high_low
    money_volume = multiplier * df["Volume"]
    cmf = money_volume.rolling(length).sum() / df["Volume"].replace(0, np.nan).rolling(length).sum()
    return cmf.rename("CMF_20")


def _add_manual_channels(df: pd.DataFrame) -> pd.DataFrame:
    df["DONCHIAN_HIGH_20"] = df["High"].rolling(20).max()
    df["DONCHIAN_LOW_20"] = df["Low"].rolling(20).min()
    df["DONCHIAN_MID_20"] = (df["DONCHIAN_HIGH_20"] + df["DONCHIAN_LOW_20"]) / 2.0

    typical = (df["High"] + df["Low"] + df["Close"]) / 3.0
    volume = df["Volume"].replace(0, np.nan)
    df["VWAP_PROXY_20"] = (typical * volume).rolling(20).sum() / volume.rolling(20).sum()
    return df


def _add_keltner_fallback(df: pd.DataFrame) -> pd.DataFrame:
    if "KELTNER_UPPER_20" in df.columns and not df["KELTNER_UPPER_20"].isna().all():
        return df

    mid = ta.ema(df["Close"], length=20)
    atr = ta.atr(df["High"], df["Low"], df["Close"], length=20)
    df["KELTNER_MID_20"] = mid
    df["KELTNER_UPPER_20"] = mid + (2.0 * atr)
    df["KELTNER_LOWER_20"] = mid - (2.0 * atr)
    return df


def _alias_indicator_columns(df: pd.DataFrame) -> pd.DataFrame:
    supertrend_cols = [col for col in df.columns if col.startswith("SUPERT_")]
    supertrend_dir_cols = [col for col in df.columns if col.startswith("SUPERTd_")]
    keltner_lower_cols = [col for col in df.columns if col.startswith("KCL_")]
    keltner_mid_cols = [col for col in df.columns if col.startswith("KCB_")]
    keltner_upper_cols = [col for col in df.columns if col.startswith("KCU_")]

    if supertrend_cols:
        df["SUPERTREND"] = df[supertrend_cols[0]]
    if supertrend_dir_cols:
        df["SUPERTREND_DIR"] = df[supertrend_dir_cols[0]]
    if keltner_lower_cols:
        df["KELTNER_LOWER_20"] = df[keltner_lower_cols[0]]
    if keltner_mid_cols:
        df["KELTNER_MID_20"] = df[keltner_mid_cols[0]]
    if keltner_upper_cols:
        df["KELTNER_UPPER_20"] = df[keltner_upper_cols[0]]
    return df


def add_features(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
    """
    Adds vectorized technical features without injecting future data.
    Signal generation is responsible for using the last closed candle.
    """
    if df.empty or len(df) < 220:
        return pd.DataFrame()

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index)

    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in out.columns:
            return pd.DataFrame()

    out[["Open", "High", "Low", "Close", "Volume"]] = out[
        ["Open", "High", "Low", "Close", "Volume"]
    ].apply(pd.to_numeric, errors="coerce")

    # Trend and trend strength
    out["EMA_20"] = ta.ema(out["Close"], length=20)
    out["EMA_50"] = ta.ema(out["Close"], length=50)
    out["EMA_200"] = ta.ema(out["Close"], length=200)
    out = _append_indicator(out, ta.adx(out["High"], out["Low"], out["Close"], length=14))

    # Momentum
    out["RSI_14"] = ta.rsi(out["Close"], length=14)
    out = _append_indicator(out, ta.stochrsi(out["Close"], length=14, rsi_length=14, k=3, d=3))
    out = _append_indicator(out, ta.macd(out["Close"], fast=12, slow=26, signal=9))
    out["MFI_14"] = ta.mfi(out["High"], out["Low"], out["Close"], out["Volume"], length=14)
    if out["MFI_14"].isna().all():
        out["MFI_14"] = _manual_mfi(out, 14)
    out["CMF_20"] = _manual_cmf(out, 20)

    # Volatility and channels
    out["ATR_14"] = ta.atr(out["High"], out["Low"], out["Close"], length=14)
    out["ATR_PCT"] = out["ATR_14"] / out["Close"].replace(0, np.nan)
    out["ATR_PCT_RANK_100"] = out["ATR_PCT"].rolling(100).rank(pct=True)
    out["VOL_REGIME"] = np.select(
        [out["ATR_PCT_RANK_100"] >= 0.80, out["ATR_PCT_RANK_100"] <= 0.20],
        [1, -1],
        default=0,
    )
    out = _append_indicator(out, ta.bbands(out["Close"], length=20, std=2.0))
    out = _append_indicator(out, ta.supertrend(out["High"], out["Low"], out["Close"], length=10, multiplier=3.0))
    out = _append_indicator(out, ta.kc(out["High"], out["Low"], out["Close"], length=20, scalar=2.0))
    out = _alias_indicator_columns(out)
    out = _add_keltner_fallback(out)
    out = _add_manual_channels(out)

    # Price action
    out["Log_Ret"] = np.log(out["Close"] / out["Close"].shift(1))
    out["Range_PCT"] = (out["High"] - out["Low"]) / out["Close"].replace(0, np.nan)
    out["Body_PCT"] = (out["Close"] - out["Open"]).abs() / out["Close"].replace(0, np.nan)

    low_min = out["Low"].rolling(window=5).min()
    high_max = out["High"].rolling(window=5).max()
    rsi_min = out["RSI_14"].rolling(window=5).min()
    rsi_max = out["RSI_14"].rolling(window=5).max()
    mfi_min = out["MFI_14"].rolling(window=5).min()
    mfi_max = out["MFI_14"].rolling(window=5).max()

    out["Bull_Div"] = np.where((out["Low"] < low_min.shift(1)) & (out["RSI_14"] > rsi_min.shift(1)), 1, 0)
    out["Bear_Div"] = np.where((out["High"] > high_max.shift(1)) & (out["RSI_14"] < rsi_max.shift(1)), 1, 0)
    out["MFI_Bull_Div"] = np.where((out["Low"] < low_min.shift(1)) & (out["MFI_14"] > mfi_min.shift(1)), 1, 0)
    out["MFI_Bear_Div"] = np.where((out["High"] > high_max.shift(1)) & (out["MFI_14"] < mfi_max.shift(1)), 1, 0)

    macd_h = [c for c in out.columns if c.startswith("MACDh")]
    if macd_h:
        macd_hist = out[macd_h[0]]
        out["MACD_Bull_Div"] = np.where(
            (out["Low"] < low_min.shift(1)) & (macd_hist > macd_hist.rolling(5).min().shift(1)),
            1,
            0,
        )
        out["MACD_Bear_Div"] = np.where(
            (out["High"] > high_max.shift(1)) & (macd_hist < macd_hist.rolling(5).max().shift(1)),
            1,
            0,
        )

    required = ["EMA_50", "EMA_200", "RSI_14", "ATR_14", "Log_Ret", "MFI_14", "CMF_20"]
    out = out.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    return out


def _reset_for_asof(df: pd.DataFrame) -> pd.DataFrame:
    reset = df.copy()
    if hasattr(reset.index, "tz_localize"):
        reset.index = reset.index.tz_localize(None)
    reset.index.name = "Date"
    reset = reset.reset_index()
    if "Date" not in reset.columns:
        reset = reset.rename(columns={reset.columns[0]: "Date"})
    return reset.sort_values("Date")


def merge_mtf_data(ltf_df: pd.DataFrame, htf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges daily closed-candle context into hourly features.
    Daily features are shifted by one full daily bar to prevent lookahead bias.
    """
    if ltf_df.empty or htf_df.empty:
        return pd.DataFrame()

    ltf_features = add_features(ltf_df, timeframe="1h")
    htf_features = add_features(htf_df, timeframe="1d")
    if ltf_features.empty or htf_features.empty:
        return pd.DataFrame()

    htf_required = [col for col in ["Close", "EMA_50", "EMA_200", "RSI_14", "ATR_14"] if col in htf_features.columns]
    htf_shifted = htf_features.shift(1).dropna(subset=htf_required)
    htf_shifted.columns = [f"HTF_{col}" for col in htf_shifted.columns]

    merged = pd.merge_asof(
        _reset_for_asof(ltf_features),
        _reset_for_asof(htf_shifted),
        on="Date",
        direction="backward",
    )
    merged.set_index("Date", inplace=True)
    required = ["Close", "EMA_50", "EMA_200", "RSI_14", "ATR_14", "HTF_Close", "HTF_EMA_50"]
    required = [col for col in required if col in merged.columns]
    merged = merged.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    return merged
