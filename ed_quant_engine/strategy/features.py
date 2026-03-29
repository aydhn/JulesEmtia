import pandas_ta as ta
import numpy as np
import pandas as pd

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate essential features (indicators) based on MTF principles and robust NO-lookahead bias logic.
    Most logic happens dynamically in DataEngine / DataLoader now during merging but this
    function exposes logic for standalone backtests.
    """
    if df.empty: return df

    # EMAs
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)

    # MACD
    macd = ta.macd(df['Close'])
    if macd is not None:
        df['MACD'] = macd.iloc[:, 0]
        df['MACD_Signal'] = macd.iloc[:, 1]
        df['MACD_Hist'] = macd.iloc[:, 2]
    else:
        df['MACD'] = df['MACD_Signal'] = df['MACD_Hist'] = 0

    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)

    # ATR
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

    # Bollinger Bands
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is not None:
        df['BBL'] = bbands.iloc[:, 0]
        df['BBM'] = bbands.iloc[:, 1]
        df['BBU'] = bbands.iloc[:, 2]

    # Price Action (Returns)
    df['Returns'] = df['Close'].pct_change()

    # Z-Score (Flash Crash detection)
    df['Z_Score'] = (df['Close'] - df['Close'].rolling(50).mean()) / df['Close'].rolling(50).std()

    # Shift indicators by 1 to strictly enforce anti-lookahead bias before returning.
    features_to_shift = ['EMA_50', 'EMA_200', 'MACD', 'RSI', 'ATR', 'Z_Score']
    for col in features_to_shift:
        if col in df.columns:
            df[col] = df[col].shift(1)

    return df.dropna()
