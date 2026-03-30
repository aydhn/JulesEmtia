import pandas as pd
import numpy as np
import pandas_ta as ta

from logger import log


def add_features(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
    """
    Computes technical indicators using pandas_ta in a vectorized manner.
    Calculations strictly use 'close' (not shifted) because the MTF alignment
    (in data_loader.py) and signal generation (in strategy.py) handle the shift(1)
    to prevent lookahead bias.
    """
    if df.empty or len(df) < 200:
        log.warning(f"Dataframe too short for reliable indicator calculation (min 200).")
        return pd.DataFrame()

    try:
        df = df.copy()

        # Trend Filter (EMA 50, EMA 200)
        df['EMA_50'] = ta.ema(df['close'], length=50)
        df['EMA_200'] = ta.ema(df['close'], length=200)

        # Momentum & Overbought/Oversold (RSI 14)
        df['RSI_14'] = ta.rsi(df['close'], length=14)

        # MACD (12, 26, 9)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
        else:
            df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = np.nan, np.nan, np.nan

        # Volatility & Risk Management (ATR 14, BB 20, 2)
        # ATR is crucial for dynamic stop-loss, take-profit, and slippage modelling.
        atr = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['ATR_14'] = atr if atr is not None else np.nan

        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None and not bbands.empty:
            df['BB_Upper'] = bbands['BBU_20_2.0']
            df['BB_Lower'] = bbands['BBL_20_2.0']
        else:
            df['BB_Upper'], df['BB_Lower'] = np.nan, np.nan

        # Price Action (Log Returns)
        df['Log_Return'] = np.log(df['close'] / df['close'].shift(1))

        # Handle NaNs from lookback periods (e.g. first 200 rows of EMA_200)
        df.dropna(inplace=True)

        # Append suffix if calculating on Higher Timeframe to differentiate columns
        if is_htf:
            df.columns = [f"{c}_htf" if c not in ['open', 'high', 'low', 'close', 'volume'] else c for c in df.columns]

        return df

    except Exception as e:
        log.error(f"Failed to compute features: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    import asyncio
    from data_loader import fetch_mtf_data, align_mtf_data, UNIVERSE

    async def test():
        ticker = UNIVERSE["Gold"]
        print(f"Testing Features for {ticker}...")
        htf, ltf = await fetch_mtf_data(ticker, "2y", "60d")

        # Calculate features on individual timeframes BEFORE alignment
        htf_feat = add_features(htf, is_htf=True)
        ltf_feat = add_features(ltf, is_htf=False)

        # Align
        aligned = align_mtf_data(htf_feat, ltf_feat)
        print("Aligned MTF Tail:\n", aligned.tail()[['close', 'EMA_50', 'RSI_14', 'EMA_50_htf_htf']]) # suffix applied twice for clarity in test

    asyncio.run(test())
