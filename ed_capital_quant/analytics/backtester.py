import pandas as pd
import numpy as np

def run_backtest(df: pd.DataFrame, signals: pd.Series, slippage=0.001, commission=0.0005) -> dict:
    # A simplified vectorized backtest
    df['Signal'] = signals
    df['Position'] = df['Signal'].shift(1).fillna(0)
    df['Strategy_Return'] = df['Position'] * df['Returns']

    # Apply costs
    trades = df['Position'].diff().abs()
    costs = trades * (slippage + commission)
    df['Strategy_Return_Net'] = df['Strategy_Return'] - costs

    cumulative_return = (1 + df['Strategy_Return_Net']).cumprod()
    max_drawdown = (cumulative_return.cummax() - cumulative_return) / cumulative_return.cummax()

    win_rate = len(df[df['Strategy_Return_Net'] > 0]) / max(1, len(df[df['Strategy_Return_Net'] != 0]))

    return {
        "Total_Return": cumulative_return.iloc[-1] - 1,
        "Max_Drawdown": max_drawdown.max(),
        "Win_Rate": win_rate
    }
