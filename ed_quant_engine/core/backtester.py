import pandas as pd
import numpy as np
import itertools
from typing import Dict, Any, List, Tuple

from .quant_models import add_features
from .config import INITIAL_CAPITAL, SPREADS, TICKERS
from .infrastructure import logger

class FastBacktester:
    """Phase 7: Vectorized Historical Backtesting Engine."""

    def __init__(self, df: pd.DataFrame, ticker: str):
        self.df = df.copy()
        self.ticker = ticker

        # Determine base spread (Phase 21)
        category = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")
        self.base_spread = SPREADS.get(category, 0.001)

    def run_backtest(self, rsi_ob=70, rsi_os=30, atr_sl_mult=1.5, atr_tp_mult=3.0) -> Dict[str, Any]:
        """Runs a vectorized backtest over the dataframe."""
        df = self.df.copy()

        # 1. Signal Generation (Vectorized Phase 4)
        # Long Conditions
        trend_up = df['Close'] > df['EMA_50']
        rsi_bull = (df['RSI_14'].shift(1) < rsi_os) & (df['RSI_14'] >= rsi_os)

        # Short Conditions
        trend_down = df['Close'] < df['EMA_50']
        rsi_bear = (df['RSI_14'].shift(1) > rsi_ob) & (df['RSI_14'] <= rsi_ob)

        df['Signal'] = 0
        df.loc[trend_up & rsi_bull, 'Signal'] = 1
        df.loc[trend_down & rsi_bear, 'Signal'] = -1

        # 2. Execution Simulation
        trades = []
        in_position = 0 # 1 for Long, -1 for Short
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        entry_idx = None

        # We must iterate for path-dependent Trailing Stops and TP/SL hits
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]

            # Check for exits if in position
            if in_position == 1:
                # Hit SL (Low went below SL)
                if row['Low'] <= sl_price:
                    exit_price = sl_price - (self.base_spread / 2) - (0.5 * row['ATRr_14']) # Slippage
                    pnl = (exit_price - entry_price) / entry_price
                    trades.append({'type': 'Long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    in_position = 0
                # Hit TP (High went above TP)
                elif row['High'] >= tp_price:
                    exit_price = tp_price - (self.base_spread / 2) - (0.5 * row['ATRr_14'])
                    pnl = (exit_price - entry_price) / entry_price
                    trades.append({'type': 'Long', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    in_position = 0
                else:
                    # Trailing Stop Update (Phase 12)
                    new_sl = row['Close'] - (atr_sl_mult * row['ATRr_14'])
                    if new_sl > sl_price:
                        sl_price = new_sl

            elif in_position == -1:
                if row['High'] >= sl_price:
                    exit_price = sl_price + (self.base_spread / 2) + (0.5 * row['ATRr_14'])
                    pnl = (entry_price - exit_price) / entry_price
                    trades.append({'type': 'Short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    in_position = 0
                elif row['Low'] <= tp_price:
                    exit_price = tp_price + (self.base_spread / 2) + (0.5 * row['ATRr_14'])
                    pnl = (entry_price - exit_price) / entry_price
                    trades.append({'type': 'Short', 'entry': entry_price, 'exit': exit_price, 'pnl': pnl})
                    in_position = 0
                else:
                    # Trailing Stop Update
                    new_sl = row['Close'] + (atr_sl_mult * row['ATRr_14'])
                    if new_sl < sl_price:
                        sl_price = new_sl

            # Check for entries if flat
            if in_position == 0:
                signal = prev_row['Signal'] # Use previous closed candle signal
                if signal == 1:
                    in_position = 1
                    entry_price = row['Open'] + (self.base_spread / 2) + (0.5 * row['ATRr_14'])
                    sl_price = entry_price - (atr_sl_mult * row['ATRr_14'])
                    tp_price = entry_price + (atr_tp_mult * row['ATRr_14'])
                elif signal == -1:
                    in_position = -1
                    entry_price = row['Open'] - (self.base_spread / 2) - (0.5 * row['ATRr_14'])
                    sl_price = entry_price + (atr_sl_mult * row['ATRr_14'])
                    tp_price = entry_price - (atr_tp_mult * row['ATRr_14'])

        # 3. Calculate Metrics
        trades_df = pd.DataFrame(trades)
        if trades_df.empty:
            return {"win_rate": 0, "profit_factor": 0, "total_pnl": 0, "trades": 0, "max_dd": 0}

        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]

        win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1e-9
        profit_factor = gross_profit / gross_loss

        # Cumulative PnL for Drawdown
        trades_df['cum_pnl'] = (1 + trades_df['pnl']).cumprod()
        running_max = trades_df['cum_pnl'].cummax()
        drawdown = (running_max - trades_df['cum_pnl']) / running_max
        max_dd = drawdown.max()

        total_pnl_pct = trades_df['cum_pnl'].iloc[-1] - 1 if not trades_df.empty else 0

        return {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl_pct,
            "trades": len(trades_df),
            "max_dd": max_dd
        }

    def grid_search_optimization(self) -> Dict[str, Any]:
        """CPU Friendly Grid Search for RSI & ATR parameters."""
        logger.info(f"Running Grid Search Optimization for {self.ticker}...")

        rsi_os_range = [25, 30, 35]
        atr_sl_range = [1.5, 2.0]
        atr_tp_range = [2.0, 3.0]

        best_result = None
        best_params = None
        max_pnl = -float('inf')

        for rsi_os, atr_sl, atr_tp in itertools.product(rsi_os_range, atr_sl_range, atr_tp_range):
            rsi_ob = 100 - rsi_os
            result = self.run_backtest(rsi_ob=rsi_ob, rsi_os=rsi_os, atr_sl_mult=atr_sl, atr_tp_mult=atr_tp)

            # Optimization Goal: Highest PnL with acceptable Win Rate and Drawdown
            if result['trades'] > 5 and result['win_rate'] > 0.40 and result['max_dd'] < 0.25:
                if result['total_pnl'] > max_pnl:
                    max_pnl = result['total_pnl']
                    best_result = result
                    best_params = {"rsi_os": rsi_os, "rsi_ob": rsi_ob, "atr_sl": atr_sl, "atr_tp": atr_tp}

        return {"best_params": best_params, "best_metrics": best_result}
