import pandas as pd
import pandas_ta as ta
import numpy as np
from ed_quant_engine.utils.logger import setup_logger

logger = setup_logger("FeatureEngine")

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Adds technical indicators to the OHLCV DataFrame avoiding lookahead bias."""
    try:
        # EMA for Trend (Main direction)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_200'] = ta.ema(df['Close'], length=200)

        # Momentum & Overbought/Oversold
        df['RSI_14'] = ta.rsi(df['Close'], length=14)

        macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_Hist'] = macd['MACDh_12_26_9']
            df['MACD_Signal'] = macd['MACDs_12_26_9']

        # Volatility & Risk Management (JP Morgan Approach)
        df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)

        bbands = ta.bbands(df['Close'], length=20, std=2.0)
        if bbands is not None:
             df['BBL_20_2.0'] = bbands['BBL_20_2.0']
             df['BBM_20_2.0'] = bbands['BBM_20_2.0']
             df['BBU_20_2.0'] = bbands['BBU_20_2.0']

        # Price Action (Returns)
        df['Returns'] = df['Close'].pct_change()
        df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))

        # Drop rows with NaNs caused by lookback periods
        df.dropna(inplace=True)

        return df
    except Exception as e:
        logger.error(f"Error adding features: {e}")
        return df

def align_mtf_data(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aligns Daily (HTF) data to Hourly (LTF) data without lookahead bias.
    Crucial Quant Rule: Use shift(1) on HTF before merging so current hour only sees yesterday's close.
    """
    try:
        # Shift HTF by 1 to represent yesterday's data for today's hours
        htf_shifted = htf_df.shift(1).copy()

        # Ensure indices are timezone-aware or naive consistently
        if htf_shifted.index.tz is not None and ltf_df.index.tz is None:
             htf_shifted.index = htf_shifted.index.tz_localize(None)
        elif htf_shifted.index.tz is None and ltf_df.index.tz is not None:
             htf_shifted.index = htf_shifted.index.tz_localize('UTC') # Example

        # Merge_asof requires sorted indices
        htf_shifted.sort_index(inplace=True)
        ltf_df.sort_index(inplace=True)

        merged_df = pd.merge_asof(
            ltf_df,
            htf_shifted.add_prefix('HTF_'),
            left_index=True,
            right_index=True,
            direction='backward'
        )
        # Forward fill the HTF values for the whole day's hours
        merged_df.ffill(inplace=True)
        return merged_df

    except Exception as e:
        logger.error(f"Error aligning MTF data: {e}")
        return ltf_df
