import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, data: pd.DataFrame, initial_capital=10000):
        self.data = data
        self.initial_capital = initial_capital

    def run_vectorized_backtest(self, signals: pd.Series):
        # Placeholder for vectorized fast-backtest engine
        # Usually computes entries, exits, slippage on static historical signals
        # Simulating returns for now.
        returns = signals.shift(1) * self.data['Returns']

        # Adding slippage constraint (0.1% per trade simulated via reduced returns)
        turnover = signals.diff().abs()
        returns = returns - (turnover * 0.001)

        cumulative = (1 + returns).cumprod() * self.initial_capital

        win_rate = len(returns[returns > 0]) / len(returns[returns != 0]) if len(returns[returns != 0]) > 0 else 0

        return {
            "Total_Return": cumulative.iloc[-1] if not cumulative.empty else self.initial_capital,
            "Win_Rate": win_rate
        }
