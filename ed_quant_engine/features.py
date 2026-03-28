import pandas as pd
import pandas_ta as ta

def add_features(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
    """Calculates vectorised technical indicators (RSI, MACD, ATR, BB, EMA)."""
    # Prevent SettingWithCopyWarning
    df = df.copy()

    # Handle yfinance MultiIndex columns if present (e.g. ('Close', 'GC=F'))
    if isinstance(df.columns, pd.MultiIndex):
        close_col = [c for c in df.columns if c[0] == 'Close'][0]
        high_col = [c for c in df.columns if c[0] == 'High'][0]
        low_col = [c for c in df.columns if c[0] == 'Low'][0]
    else:
        close_col, high_col, low_col = 'Close', 'High', 'Low'

    # Suffix for multi-timeframe differentiation if needed
    sfx = "_HTF" if is_htf else ""

    df[f"EMA_50{sfx}"] = ta.ema(df[close_col], length=50)
    df[f"EMA_200{sfx}"] = ta.ema(df[close_col], length=200)

    df[f"RSI_14{sfx}"] = ta.rsi(df[close_col], length=14)

    macd = ta.macd(df[close_col], fast=12, slow=26, signal=9)
    if macd is not None:
        df[f"MACD{sfx}"] = macd[macd.columns[0]]  # MACD line
        df[f"MACD_Hist{sfx}"] = macd[macd.columns[1]] # Histogram
        df[f"MACD_Signal{sfx}"] = macd[macd.columns[2]] # Signal

    # ATR for Risk Management
    df[f"ATR_14{sfx}"] = ta.atr(df[high_col], df[low_col], df[close_col], length=14)

    # Bollinger Bands
    bb = ta.bbands(df[close_col], length=20, std=2)
    if bb is not None:
        df[f"BB_Lower{sfx}"] = bb[bb.columns[0]] # Lower
        df[f"BB_Mid{sfx}"] = bb[bb.columns[1]]   # Mid
        df[f"BB_Upper{sfx}"] = bb[bb.columns[2]] # Upper

    # Price Action: log returns (pct_change is simpler for vectorized usage)
    df[f"Return{sfx}"] = df[close_col].pct_change()

    # Shift all indicators to completely eliminate lookahead bias at the signal generation phase
    # The current row's indicators will represent the state of the *previous* closed candle.
    for col in df.columns:
        if col not in [close_col, high_col, low_col]:
            df[col] = df[col].shift(1)

    return df.dropna()
