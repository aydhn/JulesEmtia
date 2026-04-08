import pandas as pd
import pandas_ta as ta
import numpy as np

def add_features(df: pd.DataFrame, timeframe="1h") -> pd.DataFrame:
    """
    Applies technical indicators. MUST avoid lookahead bias by not shifting here,
    shifting will be done at the strategy level or MTF merge.
    """
    if df.empty or len(df) < 200:
        return df

    # Ensure index is datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Trend
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    # ADX (Trend Strength)
    adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    if adx is not None:
        df = pd.concat([df, adx], axis=1)

    # Momentum
    df['RSI_14'] = ta.rsi(df['Close'], length=14)

    # Stochastic RSI
    stochrsi = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
    if stochrsi is not None:
        df = pd.concat([df, stochrsi], axis=1)

    macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # Volatility
    df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    bbands = ta.bbands(df['Close'], length=20, std=2.0)
    if bbands is not None:
        df = pd.concat([df, bbands], axis=1)

    # Price Action
    df['Log_Ret'] = np.log(df['Close'] / df['Close'].shift(1))

    # Calculate Divergences (Bullish/Bearish)
    # Simple bullish divergence: Price makes lower low, RSI makes higher low
    low_min = df['Low'].rolling(window=5).min()
    rsi_min = df['RSI_14'].rolling(window=5).min()
    df['Bull_Div'] = np.where((df['Low'] < low_min.shift(1)) & (df['RSI_14'] > rsi_min.shift(1)), 1, 0)

    # Simple bearish divergence: Price makes higher high, RSI makes lower high
    high_max = df['High'].rolling(window=5).max()
    rsi_max = df['RSI_14'].rolling(window=5).max()
    df['Bear_Div'] = np.where((df['High'] > high_max.shift(1)) & (df['RSI_14'] < rsi_max.shift(1)), 1, 0)

    # MACD Divergences
    macd_h = [c for c in df.columns if c.startswith('MACDh')]
    if macd_h:
        macd_hist = df[macd_h[0]]
        macd_hist_min = macd_hist.rolling(window=5).min()
        macd_hist_max = macd_hist.rolling(window=5).max()
        df['MACD_Bull_Div'] = np.where((df['Low'] < low_min.shift(1)) & (macd_hist > macd_hist_min.shift(1)), 1, 0)
        df['MACD_Bear_Div'] = np.where((df['High'] > high_max.shift(1)) & (macd_hist < macd_hist_max.shift(1)), 1, 0)

    df.dropna(inplace=True)
    return df

def merge_mtf_data(ltf_df: pd.DataFrame, htf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges High Timeframe (Daily) indicators into Low Timeframe (Hourly) data.
    Strictly prevents lookahead bias using shift(1) on HTF and merge_asof.
    """
    if ltf_df.empty or htf_df.empty:
        return pd.DataFrame()

    # Calculate HTF features first
    htf_df = add_features(htf_df, timeframe="1d")

    # Shift HTF data by 1 period to prevent lookahead bias!
    # Today's hourly candles can only see YESTERDAY's closed daily candle.
    htf_shifted = htf_df.shift(1).dropna()

    # Rename columns to identify them as HTF
    htf_shifted.columns = [f"HTF_{col}" for col in htf_shifted.columns]

    # Ensure timezone naive
    if hasattr(ltf_df.index, 'tz_localize'):
        ltf_df.index = ltf_df.index.tz_localize(None)
    if hasattr(htf_shifted.index, 'tz_localize'):
        htf_shifted.index = htf_shifted.index.tz_localize(None)

    # Reset index for merge_asof
    ltf_df = ltf_df.reset_index()
    htf_shifted = htf_shifted.reset_index()

    # Use merge_asof with direction='backward' to align timestamps safely
    merged_df = pd.merge_asof(
        ltf_df.sort_values('Date'),
        htf_shifted.sort_values('Date'),
        on='Date',
        direction='backward'
    )

    merged_df.set_index('Date', inplace=True)
    return merged_df
