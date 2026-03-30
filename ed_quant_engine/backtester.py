import pandas as pd
import numpy as np
from logger import logger
import matplotlib.pyplot as plt
import io
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed

class Backtester:
    def __init__(self, initial_capital=10000.0, commission=0.0005, slippage=0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.trades = []

    def run_vectorized_backtest(self, df: pd.DataFrame, direction_col='Direction', entry_col='Close', sl_col='SL', tp_col='TP'):
        '''
        Phase 7: Fast Iterative/Vectorized Backtest Engine
        Simulates entry, SL, TP, and trailing stops with realistic slippage and commission.
        '''
        if df.empty or direction_col not in df.columns:
            return pd.DataFrame()

        capital = self.initial_capital
        equity_curve = [capital]
        self.trades = []

        in_position = False
        entry_price = 0.0
        current_sl = 0.0
        current_tp = 0.0
        direction = None
        entry_time = None
        size = 0.0

        for idx, row in df.iterrows():
            # Check exit conditions first if in position
            if in_position:
                exit_price = 0.0
                reason = None

                # Check for TP or SL hit
                if direction == 'Long':
                    if row['High'] >= current_tp:
                        exit_price = current_tp
                        reason = 'TP'
                    elif row['Low'] <= current_sl:
                        exit_price = current_sl
                        reason = 'SL'
                elif direction == 'Short':
                    if row['Low'] <= current_tp:
                        exit_price = current_tp
                        reason = 'TP'
                    elif row['High'] >= current_sl:
                        exit_price = current_sl
                        reason = 'SL'

                if reason:
                    # Apply slippage and commission to exit
                    exit_cost = exit_price * (self.commission + self.slippage)
                    if direction == 'Long':
                        exit_price_actual = exit_price - exit_cost
                        pnl = (exit_price_actual - entry_price) * size
                    else:
                        exit_price_actual = exit_price + exit_cost
                        pnl = (entry_price - exit_price_actual) * size

                    capital += pnl
                    self.trades.append({
                        'entry_time': entry_time,
                        'exit_time': idx,
                        'direction': direction,
                        'entry_price': entry_price,
                        'exit_price': exit_price_actual,
                        'pnl': pnl,
                        'reason': reason
                    })
                    in_position = False
                else:
                    # Implement simple trailing stop logic for backtest approximation
                    atr = row.get('ATR_14', (row['High'] - row['Low']))
                    if direction == 'Long' and row['Close'] > (current_sl + 1.5 * atr):
                        new_sl = row['Close'] - (1.5 * atr)
                        if new_sl > current_sl:
                            current_sl = new_sl
                    elif direction == 'Short' and row['Close'] < (current_sl - 1.5 * atr):
                        new_sl = row['Close'] + (1.5 * atr)
                        if new_sl < current_sl:
                            current_sl = new_sl

            # Check for entry signals if not in position
            if not in_position and pd.notna(row.get(direction_col)):
                direction = row[direction_col]
                # Apply slippage and commission to entry
                raw_entry = row[entry_col]
                entry_cost = raw_entry * (self.commission + self.slippage)

                if direction == 'Long':
                    entry_price = raw_entry + entry_cost
                else:
                    entry_price = raw_entry - entry_cost

                current_sl = row.get(sl_col, entry_price * 0.98 if direction=='Long' else entry_price * 1.02)
                current_tp = row.get(tp_col, entry_price * 1.04 if direction=='Long' else entry_price * 0.96)

                # Simplified 2% risk size
                risk_amount = capital * 0.02
                sl_dist = abs(entry_price - current_sl)
                size = risk_amount / sl_dist if sl_dist > 0 else 0

                if size > 0:
                    in_position = True
                    entry_time = idx

            equity_curve.append(capital)

        return pd.DataFrame({'equity': equity_curve[1:]}, index=df.index)

    def calculate_metrics(self, benchmark_returns=None):
        ''' Returns Win Rate, Profit Factor, Max Drawdown '''
        if not self.trades:
            return {"Total PnL": 0, "Win Rate": 0, "Profit Factor": 0, "Max Drawdown": 0}

        df_trades = pd.DataFrame(self.trades)
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]

        win_rate = len(wins) / len(df_trades)

        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
        profit_factor = gross_profit / gross_loss

        total_pnl = df_trades['pnl'].sum()

        # Max Drawdown Approximation
        cumulative = (df_trades['pnl'].cumsum() + self.initial_capital)
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        max_drawdown = drawdown.min()

        metrics = {
            "Total PnL": total_pnl,
            "Win Rate": win_rate,
            "Profit Factor": profit_factor,
            "Max Drawdown": max_drawdown,
            "Total Trades": len(df_trades)
        }
        return metrics

    def _run_single_grid_point(self, args):
        params, df, strategy_func = args
        # Apply parameters to strategy function (mocked here)
        # In a real implementation, strategy_func generates the 'Direction', 'SL', 'TP' columns
        # df_signaled = strategy_func(df.copy(), **params)
        df_signaled = df.copy() # Placeholder

        equity_df = self.run_vectorized_backtest(df_signaled)
        metrics = self.calculate_metrics()
        return (params, metrics)

    def optimize_parameters(self, df: pd.DataFrame, params_grid: dict, strategy_func):
        ''' Phase 7: CPU Friendly Grid Search '''
        logger.info("Starting Grid Search Optimization...")

        keys, values = zip(*params_grid.items())
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

        best_metrics = None
        best_params = None

        # CPU friendly multiprocessing
        tasks = [(params, df, strategy_func) for params in combinations]

        with ProcessPoolExecutor() as executor:
            futures = {executor.submit(self._run_single_grid_point, task): task for task in tasks}
            for future in as_completed(futures):
                params, metrics = future.result()

                # Optimize for Profit Factor * Win Rate as a combined score
                score = metrics.get('Profit Factor', 0) * metrics.get('Win Rate', 0)

                if best_metrics is None or score > (best_metrics.get('Profit Factor', 0) * best_metrics.get('Win Rate', 0)):
                    best_metrics = metrics
                    best_params = params

        logger.info(f"Optimization Complete. Best Params: {best_params} | Metrics: {best_metrics}")
        return best_params, best_metrics
