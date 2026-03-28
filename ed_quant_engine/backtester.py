import pandas as pd
import numpy as np

# Phase 7 & 21: Historical Backtesting Engine (Vectorized)
class Backtester:
    def __init__(self, df: pd.DataFrame, initial_capital=10000.0, commission=0.0005, slippage=0.001):
        self.df = df.copy()
        self.capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run_backtest(self) -> dict:
        self.df['Signal'] = 0
        self.df['Position'] = 0

        # Long Conditions
        long_cond = (self.df['HTF_Trend'].shift(1) == 1) & ((self.df['RSI'].shift(1) < 30) | (self.df['Close'].shift(1) <= self.df['BB_Lower'].shift(1)))

        # Short Conditions
        short_cond = (self.df['HTF_Trend'].shift(1) == -1) & ((self.df['RSI'].shift(1) > 70) | (self.df['Close'].shift(1) >= self.df['BB_Upper'].shift(1)))

        self.df.loc[long_cond, 'Signal'] = 1
        self.df.loc[short_cond, 'Signal'] = -1

        # Simulate Entry/Exit limits
        self.df['Position'] = self.df['Signal'].replace(to_replace=0, method='ffill')

        # Calculate Returns
        self.df['Strategy_Returns'] = self.df['Position'].shift(1) * self.df['Returns']

        # Subtract costs on signal changes
        trade_occurred = self.df['Signal'] != 0
        self.df.loc[trade_occurred, 'Strategy_Returns'] -= (self.commission + self.slippage)

        # Cumulative PnL
        self.df['Cumulative_Returns'] = (1 + self.df['Strategy_Returns']).cumprod()
        self.df['Equity'] = self.capital * self.df['Cumulative_Returns']

        # Metrics calculation
        win_rate = len(self.df[self.df['Strategy_Returns'] > 0]) / len(self.df[self.df['Strategy_Returns'] != 0]) if len(self.df[self.df['Strategy_Returns'] != 0]) > 0 else 0

        gross_profit = self.df[self.df['Strategy_Returns'] > 0]['Strategy_Returns'].sum()
        gross_loss = abs(self.df[self.df['Strategy_Returns'] < 0]['Strategy_Returns'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 1.0

        peak = self.df['Cumulative_Returns'].cummax()
        drawdown = (peak - self.df['Cumulative_Returns']) / peak
        max_drawdown = drawdown.max() * 100

        total_pnl = self.df['Equity'].iloc[-1] - self.capital

        return {
            "Total_PnL": total_pnl,
            "Win_Rate": win_rate * 100,
            "Profit_Factor": profit_factor,
            "Max_Drawdown": max_drawdown
        }
