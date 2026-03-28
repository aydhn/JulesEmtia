import pandas as pd
import pandas_ta as ta
from core.logger import setup_logger

logger = setup_logger("features")

def add_technical_indicators(df: pd.DataFrame, is_htf: bool = False) -> pd.DataFrame:
    """
    Adds core technical indicators using pandas_ta:
    EMA 50, EMA 200, RSI 14, MACD, ATR 14, and Bollinger Bands.
    """
    df = df.copy()

    # Log returns (Price Action)
    df['log_return'] = df['close'] / df['close'].shift(1) - 1.0

    # Moving Averages
    df['ema_50'] = ta.ema(df['close'], length=50)
    df['ema_200'] = ta.ema(df['close'], length=200)

    # Momentum
    df['rsi_14'] = ta.rsi(df['close'], length=14)
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)

    # Volatility & Risk Management
    df['atr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)

    # Bollinger Bands
    bbands = ta.bbands(df['close'], length=20, std=2)
    df = pd.concat([df, bbands], axis=1)

    # Quant Discipline: Shift indicators by 1 period to prevent Lookahead Bias
    # This ensures that when generating a signal at time 't', we only use data known at 't-1'
    # EXCEPT for the current close price, which is needed for the entry price calculation.

    # The shifting mechanism will be handled in strategy.py to allow dynamic ATR access.
    # However, for pure signal generation, the shifted values must be used.
    # We will create shifted columns specifically for signal logic.

    cols_to_shift = [
        'ema_50', 'ema_200', 'rsi_14',
        'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9',
        'atr_14', 'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0'
    ]

    for col in cols_to_shift:
        if col in df.columns:
            df[f'{col}_prev'] = df[col].shift(1)

    # Clean initial NaNs caused by lookback periods (e.g., EMA 200 needs 200 rows)
    # Be careful not to drop the entire dataframe if it's too small.
    if len(df) > 200:
        df.dropna(subset=['ema_200_prev'], inplace=True)
    else:
        logger.warning(f"DataFrame length ({len(df)}) too short for full indicator warmup. Dropping NaNs where possible.")
        df.dropna(inplace=True)

    return df
