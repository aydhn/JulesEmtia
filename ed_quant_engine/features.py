import pandas as pd
import pandas_ta as ta
import numpy as np

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Phase 3: Calculates high-accuracy, zero lookahead-bias technical indicators using pandas_ta.
    """
    if df.empty or len(df) < 200:
        return df

    # Vectorized operations. Always copy to prevent SettingWithCopyWarning
    df_copy = df.copy()

    # Calculate EMAs for Trend (Adds 'EMA_50' and 'EMA_200')
    df_copy.ta.ema(length=50, append=True)
    df_copy.ta.ema(length=200, append=True)

    # Momentum (Adds 'RSI_14' and MACD columns: 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9')
    df_copy.ta.rsi(length=14, append=True)
    df_copy.ta.macd(fast=12, slow=26, signal=9, append=True)

    # Volatility / Risk Profile (Adds 'ATRr_14' and Bollinger Bands: 'BBL_20_2.0', 'BBU_20_2.0', etc.)
    df_copy.ta.atr(length=14, append=True)
    df_copy.ta.bbands(length=20, std=2, append=True)

    # Price Action (Log Return) - Shift(1) guarantees zero lookahead bias
    df_copy['Log_Return'] = np.log(df_copy['Close'] / df_copy['Close'].shift(1))

    # Clean up NaNs strictly created by indicator lookbacks (e.g., first 200 rows of EMA)
    df_copy.dropna(inplace=True)

    return df_copy

if __name__ == "__main__":
    # Test block
    print("Testing Features Module...")
    df_test = pd.DataFrame({
        'Open': np.random.randn(300) + 100,
        'High': np.random.randn(300) + 105,
        'Low': np.random.randn(300) + 95,
        'Close': np.random.randn(300) + 100,
        'Volume': np.random.randint(100, 1000, 300)
    })
    df_features = add_features(df_test)
    print("Columns Generated:", df_features.columns.tolist())
    print(df_features.tail())
