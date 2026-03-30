import pandas as pd
import numpy as np

def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure no lookahead bias by shifting signals to the previous closed candle
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_EMA_50'] = df['EMA_50'].shift(1)
    df['Prev_EMA_200'] = df['EMA_200'].shift(1)
    df['Prev_RSI'] = df['RSI_14'].shift(1)
    df['Prev_MACDh'] = df['MACDh'].shift(1)
    df['Prev_BBL'] = df['BBL'].shift(1)
    df['Prev_BBU'] = df['BBU'].shift(1)

    # Buy Signal Logic
    buy_cond_trend = df['Prev_Close'] > df['Prev_EMA_50']
    buy_cond_rsi = df['Prev_RSI'] < 30
    buy_cond_bb = df['Prev_Close'] <= df['Prev_BBL']
    buy_cond_macd = df['Prev_MACDh'] > 0

    df['Signal'] = np.where(buy_cond_trend & (buy_cond_rsi | buy_cond_bb) & buy_cond_macd, 1, 0)

    # Sell Signal Logic
    sell_cond_trend = df['Prev_Close'] < df['Prev_EMA_50']
    sell_cond_rsi = df['Prev_RSI'] > 70
    sell_cond_bb = df['Prev_Close'] >= df['Prev_BBU']
    sell_cond_macd = df['Prev_MACDh'] < 0

    df['Signal'] = np.where(sell_cond_trend & (sell_cond_rsi | sell_cond_bb) & sell_cond_macd, -1, df['Signal'])

    return df
