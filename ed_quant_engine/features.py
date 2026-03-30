import pandas as pd
import pandas_ta as ta
import numpy as np
from logger import logger

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Adds technical indicators to the MTF dataframe.
    Calculations strictly use closed candles (handled upstream or by using appropriate shift/indexing).
    The daily MTF calculations are already done in data_loader.py BEFORE the merge to ensure
    mathematical accuracy (e.g. 50 periods = 50 days, not 50 hours).
    '''
    if df.empty:
        return df

    try:
        df = df.copy()

        # Use 1h columns for LTF indicators
        close_col = 'Close'
        high_col = 'High'
        low_col = 'Low'

        # Check if columns exist
        if not all(c in df.columns for c in [close_col, high_col, low_col]):
             logger.warning("Required columns missing for features calculation.")
             return pd.DataFrame()

        # Phase 3: Trend
        df['EMA_50'] = ta.ema(df[close_col], length=50)
        df['EMA_200'] = ta.ema(df[close_col], length=200)

        # Phase 3: Momentum
        df['RSI_14'] = ta.rsi(df[close_col], length=14)

        macd = ta.macd(df[close_col], fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            df = pd.concat([df, macd], axis=1)
            # rename for consistent access
            df.rename(columns={
                'MACD_12_26_9': 'MACD',
                'MACDh_12_26_9': 'MACD_hist',
                'MACDs_12_26_9': 'MACD_signal'
            }, inplace=True)

        # Phase 3: Volatility & Risk Management
        atr = ta.atr(df[high_col], df[low_col], df[close_col], length=14)
        if atr is not None:
             df['ATR_14'] = atr

        bbands = ta.bbands(df[close_col], length=20, std=2)
        if bbands is not None and not bbands.empty:
             df = pd.concat([df, bbands], axis=1)
             df.rename(columns={
                'BBL_20_2.0': 'BB_lower',
                'BBM_20_2.0': 'BB_mid',
                'BBU_20_2.0': 'BB_upper'
             }, inplace=True)

        # Phase 3: Price Action
        df['Log_Return'] = np.log(df[close_col] / df[close_col].shift(1))
        df['Pct_Change'] = df[close_col].pct_change()

        df.dropna(inplace=True)
        return df
    except Exception as e:
        logger.error(f"Error calculating features: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    import asyncio
    from data_loader import fetch_mtf_data

    async def test():
        df = await fetch_mtf_data("GC=F")
        if not df.empty:
            df_feat = add_features(df)
            print(df_feat.tail())
    asyncio.run(test())
