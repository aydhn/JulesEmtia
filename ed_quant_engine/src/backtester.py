import pandas as pd
import numpy as np
from typing import Dict, List, Any
from src.logger import get_logger

logger = get_logger("backtester")

def vectorized_backtest(df: pd.DataFrame, initial_balance: float = 10000.0, commission_pct: float = 0.0005) -> Dict[str, Any]:
    """A vectorized backtesting engine suitable for parameter optimization."""
    if df.empty or len(df) < 200:
        return {"Error": "Insufficient data"}

    df_bt = df.copy()

    # Pre-compute signals using vector operations matching strategy.py logic
    # Simplified version for speed during optimization grids

    # Daily trend definition
    df_bt['HTF_Up'] = (df_bt['Close_HTF'] > df_bt['EMA_50_HTF']) & (df_bt['MACD_HTF'] > 0)
    df_bt['HTF_Down'] = (df_bt['Close_HTF'] < df_bt['EMA_50_HTF']) & (df_bt['MACD_HTF'] < 0)

    df_bt['LTF_Buy'] = (df_bt['RSI_14'] < 30) | (df_bt['Close'] <= df_bt['BB_Lower'])
    df_bt['LTF_Sell'] = (df_bt['RSI_14'] > 70) | (df_bt['Close'] >= df_bt['BB_Upper'])

    df_bt['MACD_Cross_Up'] = df_bt['MACD'] > df_bt['MACD_Signal']
    df_bt['MACD_Cross_Down'] = df_bt['MACD'] < df_bt['MACD_Signal']

    # Generate Long/Short signals (1: Long, -1: Short, 0: Hold)
    conditions = [
        df_bt['HTF_Up'] & df_bt['LTF_Buy'] & df_bt['MACD_Cross_Up'],
        df_bt['HTF_Down'] & df_bt['LTF_Sell'] & df_bt['MACD_Cross_Down']
    ]
    choices = [1, -1]
    df_bt['Signal'] = np.select(conditions, choices, default=0)

    # Calculate returns of holding the asset (Close-to-Close)
    df_bt['Next_Return'] = df_bt['Close'].shift(-1) / df_bt['Close'] - 1.0

    # Strategy Return: Trade taken * Next_Return - Commission
    df_bt['Strategy_Return'] = np.where(df_bt['Signal'] != 0, (df_bt['Signal'] * df_bt['Next_Return']) - commission_pct, 0.0)

    # Calculate Equity Curve
    df_bt['Cumulative_Returns'] = (1 + df_bt['Strategy_Return']).cumprod()

    # Drawdown Calculation
    df_bt['Running_Max'] = df_bt['Cumulative_Returns'].cummax()
    df_bt['Drawdown'] = (df_bt['Cumulative_Returns'] - df_bt['Running_Max']) / df_bt['Running_Max']
    max_dd = df_bt['Drawdown'].min()

    total_return = df_bt['Cumulative_Returns'].iloc[-1] - 1.0

    # Win Rate Approximation
    winning_trades = len(df_bt[df_bt['Strategy_Return'] > 0])
    losing_trades = len(df_bt[df_bt['Strategy_Return'] < 0])
    total_trades = winning_trades + losing_trades

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

    logger.debug(f"Backtest completed: Return={total_return:.2%}, MaxDD={max_dd:.2%}, WinRate={win_rate:.2%}")

    return {
        "Total_Return": total_return,
        "Max_Drawdown": max_dd,
        "Win_Rate": win_rate,
        "Total_Trades": total_trades,
        "Equity_Curve": df_bt['Cumulative_Returns']
    }
