import pandas_ta as ta
import pandas as pd
import numpy as np

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    # Use pandas_ta
    try:
        # If multiindex columns (yfinance), flatten for pandas_ta
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [f"{c[0]}" if not c[1] else f"{c[0]}_{c[1]}" for c in df.columns]

        # Explicitly specify the close column name as pandas_ta expects 'close' by default (case-insensitive)
        # Assuming the main timeframe close is 'Close'
        close_col = 'Close'
        if close_col not in df.columns:
            # try finding it if flattened differently
            possible_closes = [c for c in df.columns if 'Close' in c and not c.startswith('D1_')]
            if possible_closes:
                close_col = possible_closes[0]

        df.ta.ema(close=close_col, length=50, append=True)
        df.ta.ema(close=close_col, length=200, append=True)
        df.ta.rsi(close=close_col, length=14, append=True)
        df.ta.macd(close=close_col, append=True)

        # High, Low, Close are needed for ATR
        high_col = 'High'
        low_col = 'Low'
        if high_col not in df.columns:
             possible_highs = [c for c in df.columns if 'High' in c and not c.startswith('D1_')]
             if possible_highs: high_col = possible_highs[0]
        if low_col not in df.columns:
             possible_lows = [c for c in df.columns if 'Low' in c and not c.startswith('D1_')]
             if possible_lows: low_col = possible_lows[0]

        df.ta.atr(high=high_col, low=low_col, close=close_col, length=14, append=True)
        df.ta.bbands(close=close_col, length=20, std=2, append=True)

        df['log_ret'] = df[close_col].apply(np.log).diff()

        # Calculate daily EMA 50 on the D1_Close column if available
        d1_close_col = 'D1_Close'
        if d1_close_col in df.columns:
            df[f'D1_EMA_50'] = ta.ema(df[d1_close_col], length=50)

        df.dropna(inplace=True)
    except Exception as e:
        print(f"Error adding features: {e}")
    return df
