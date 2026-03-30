import pandas as pd
import pandas_ta as ta
import numpy as np
from logger import log

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes technical indicators without lookahead bias.
    Uses pandas_ta for efficient, vectorized operations.
    """
    if df is None or df.empty or len(df) < 200:
        return df

    df = df.copy()

    try:
        # --- Trend ---
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)

        # --- Momentum ---
        df['RSI_14'] = ta.rsi(df['Close'], length=14)

        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None:
            # MACD_12_26_9, MACDh_12_26_9 (Histogram), MACDs_12_26_9 (Signal)
            df = pd.concat([df, macd], axis=1)
            # Rename for easier access
            df.rename(columns={
                macd.columns[0]: 'MACD_line',
                macd.columns[1]: 'MACD_hist',
                macd.columns[2]: 'MACD_signal'
            }, inplace=True)

        # --- Volatility (JP Morgan Risk) ---
        df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        bbands = ta.bbands(df['Close'], length=20, std=2)
        if bbands is not None:
            df = pd.concat([df, bbands], axis=1)
            df.rename(columns={
                bbands.columns[0]: 'BB_Lower',
                bbands.columns[1]: 'BB_Mid',
                bbands.columns[2]: 'BB_Upper',
                bbands.columns[3]: 'BB_Bandwidth',
                bbands.columns[4]: 'BB_Percent'
            }, inplace=True)

        # --- Price Action ---
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Pct_Change'] = df['Close'].pct_change()

        # --- Flash Crash Detection (Z-Score) ---
        # 20-period rolling Z-score
        rolling_mean = df['Close'].rolling(window=20).mean()
        rolling_std = df['Close'].rolling(window=20).std()
        df['Z_Score'] = (df['Close'] - rolling_mean) / rolling_std

        # Clean NaNs resulting from lookback periods
        df.dropna(inplace=True)

    except Exception as e:
        log.error(f"Error calculating features: {e}")

    return df

def align_mtf_data(df_htf: pd.DataFrame, df_ltf: pd.DataFrame) -> pd.DataFrame:
    """
    Merges HTF indicators into LTF dataframe PREVENTING LOOKAHEAD BIAS.
    We shift HTF data by 1 before merge_asof, so 1H candle only sees
    the PREVIOUS fully closed 1D candle.
    """
    if df_htf.empty or df_ltf.empty:
        return pd.DataFrame()

    # Calculate features independently
    htf_feat = add_features(df_htf)
    ltf_feat = add_features(df_ltf)

    # Prefix HTF columns
    htf_feat = htf_feat.add_prefix('HTF_')

    # Shift HTF by 1 to prevent lookahead bias (today's LTF candles can only see yesterday's HTF data)
    htf_shifted = htf_feat.shift(1).dropna()

    # Reset indexes for merge_asof
    ltf_feat_reset = ltf_feat.reset_index()
    htf_shifted_reset = htf_shifted.reset_index()

    # Ensure datetime columns are named 'Date' or 'index' properly for merge
    # Yfinance usually names index 'Date' or 'Datetime'
    time_col_ltf = 'Datetime' if 'Datetime' in ltf_feat_reset.columns else 'Date' if 'Date' in ltf_feat_reset.columns else 'index'
    time_col_htf = 'Date' if 'Date' in htf_shifted_reset.columns else 'index'

    # Rename for consistency
    ltf_feat_reset.rename(columns={time_col_ltf: 'time'}, inplace=True)
    htf_shifted_reset.rename(columns={time_col_htf: 'time'}, inplace=True)

    # Merge using backward direction
    merged = pd.merge_asof(
        ltf_feat_reset.sort_values('time'),
        htf_shifted_reset.sort_values('time'),
        on='time',
        direction='backward'
    )

    merged.set_index('time', inplace=True)
    return merged
