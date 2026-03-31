import pandas as pd
import pandas_ta as ta
import numpy as np
from logger import logger

def add_features(df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
    """
    Feature Engineering & Technical Indicators Engine.
    Processes raw OHLCV data into noise-free Quant signals.
    No for-loops, pure vectorized Pandas operations.
    Follows zero lookahead bias rules.
    """
    df = df.copy()

    try:
        # 1. Trend Filter: EMA 50 & EMA 200 (Directional Bias)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)

        # 2. Momentum & Overbought/Oversold: RSI (14) & MACD (12, 26, 9)
        df['RSI_14'] = ta.rsi(df['Close'], length=14)

        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None:
            # Pandas TA MACD returns 3 columns: MACD_12_26_9, MACDh_12_26_9 (Histogram), MACDs_12_26_9 (Signal)
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_Hist'] = macd.iloc[:, 1]
            df['MACD_Signal'] = macd.iloc[:, 2]

        # 3. Volatility & Risk Management: ATR (14) & Bollinger Bands (20, 2)
        # ATR is critical for Dynamic Stop-Loss and Position Sizing (JP Morgan standard)
        df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        bbands = ta.bbands(df['Close'], length=20, std=2)
        if bbands is not None:
            df['BBL_20_2.0'] = bbands.iloc[:, 0] # Lower Band
            df['BBM_20_2.0'] = bbands.iloc[:, 1] # Middle Band
            df['BBU_20_2.0'] = bbands.iloc[:, 2] # Upper Band

        # 4. Price Action / Returns (For ML model feature engineering)
        df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))
        df['Prev_Return'] = df['Close'].pct_change().shift(1)

        # 5. Flash Crash Anomaly Detection (Z-Score) - Phase 19
        # Calculate Z-score of close price against 50-period moving average
        std_50 = df['Close'].rolling(window=50).std()
        df['Z_Score_50'] = (df['Close'] - df['EMA_50']) / std_50

        # NaN Handling: Drop rows with NaNs resulting from lookback periods
        df.dropna(inplace=True)

        return df

    except Exception as e:
        logger.error(f"Error computing technical features for {timeframe}: {e}")
        return df

