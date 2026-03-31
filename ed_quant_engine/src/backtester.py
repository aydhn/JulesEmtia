import pandas as pd
import numpy as np
from src.features import add_features
from src.strategy import Strategy
from src.data_loader import DataLoader
import asyncio
from typing import Dict, List, Tuple
from src.logger import logger
from concurrent.futures import ProcessPoolExecutor

class Backtester:
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = {k: add_features(v) for k, v in data.items() if not v.empty}
        self.strategy = Strategy()
        self.slippage = 0.001 # 0.1% slippage
        self.commission = 0.0005 # 0.05% commission

    def run_backtest(self, ticker: str, df: pd.DataFrame) -> List[Dict]:
        """
        Runs a vectorized/iterative backtest for a single ticker with slippage & commission.
        """
        trades = []
        open_trade = None

        for i in range(1, len(df)):
            current_row = df.iloc[i]
            prev_row = df.iloc[i-1]

            # Simplified backtest generation logic (not full vectorized for state handling complexity)
            signal_data = self.strategy.generate_signal(ticker, df.iloc[:i])

            if open_trade:
                # Check for exit (Hit SL or TP)
                current_price = current_row['Close']
                if open_trade['direction'] == 'Long':
                    if current_row['Low'] <= open_trade['sl_price']:
                        exit_price = open_trade['sl_price'] * (1 - self.slippage) # Slippage down on SL
                        open_trade['exit_price'] = exit_price
                        open_trade['exit_time'] = current_row.name
                        open_trade['pnl'] = (exit_price - open_trade['entry_price']) / open_trade['entry_price'] - self.commission
                        trades.append(open_trade)
                        open_trade = None
                    elif current_row['High'] >= open_trade['tp_price']:
                        exit_price = open_trade['tp_price'] * (1 - self.slippage) # Slippage down on TP
                        open_trade['exit_price'] = exit_price
                        open_trade['exit_time'] = current_row.name
                        open_trade['pnl'] = (exit_price - open_trade['entry_price']) / open_trade['entry_price'] - self.commission
                        trades.append(open_trade)
                        open_trade = None
                else: # Short
                    if current_row['High'] >= open_trade['sl_price']:
                        exit_price = open_trade['sl_price'] * (1 + self.slippage) # Slippage up on SL
                        open_trade['exit_price'] = exit_price
                        open_trade['exit_time'] = current_row.name
                        open_trade['pnl'] = (open_trade['entry_price'] - exit_price) / open_trade['entry_price'] - self.commission
                        trades.append(open_trade)
                        open_trade = None
                    elif current_row['Low'] <= open_trade['tp_price']:
                        exit_price = open_trade['tp_price'] * (1 + self.slippage) # Slippage up on TP
                        open_trade['exit_price'] = exit_price
                        open_trade['exit_time'] = current_row.name
                        open_trade['pnl'] = (open_trade['entry_price'] - exit_price) / open_trade['entry_price'] - self.commission
                        trades.append(open_trade)
                        open_trade = None

            elif signal_data: # Enter Trade
                entry_price = current_row['Open'] # Execute at open of next bar

                # Apply slippage & commission to entry
                if signal_data['direction'] == 'Long':
                    entry_price *= (1 + self.slippage)
                else:
                    entry_price *= (1 - self.slippage)

                open_trade = {
                    'ticker': ticker,
                    'direction': signal_data['direction'],
                    'entry_time': current_row.name,
                    'entry_price': entry_price,
                    'sl_price': signal_data['sl_price'],
                    'tp_price': signal_data['tp_price'],
                    'position_size': signal_data['position_size']
                }

        return trades

    def evaluate_performance(self, trades: List[Dict]) -> Dict:
        if not trades:
            return {}

        df = pd.DataFrame(trades)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        win_rate = len(wins) / len(df) if len(df) > 0 else 0
        profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')

        # Max Drawdown estimation from cumulative PnL
        cumulative_pnl = (1 + df['pnl']).cumprod()
        rolling_max = cumulative_pnl.cummax()
        drawdown = (cumulative_pnl - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        return {
            "total_trades": len(df),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": max_drawdown,
            "total_pnl": df['pnl'].sum()
        }

    def optimize_parameters(self, params_grid: List[Dict]) -> pd.DataFrame:
        """
        CPU-friendly grid search.
        """
        logger.info("Starting optimization (CPU friendly).")
        results = []
        for params in params_grid:
            self.strategy.atr_sl_multiplier = params['sl']
            self.strategy.atr_tp_multiplier = params['tp']

            all_trades = []
            for ticker, df in self.data.items():
                trades = self.run_backtest(ticker, df)
                all_trades.extend(trades)

            perf = self.evaluate_performance(all_trades)
            if perf:
                results.append({**params, **perf})

        return pd.DataFrame(results).sort_values(by="win_rate", ascending=False)
