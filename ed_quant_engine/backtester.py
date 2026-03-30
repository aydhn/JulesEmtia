import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from data_loader import DataLoader
from features import add_features, align_mtf_data
from strategy import check_entry_signal
from logger import log
from config import INITIAL_CAPITAL

class Backtester:
    def __init__(self, data_loader: DataLoader):
        self.data_loader = data_loader

    def run_backtest(self, ticker: str, start_date: str = "2020-01-01", end_date: str = "2024-01-01") -> pd.DataFrame:
        """
        Runs a vectorized/iterative backtest on historical data for a specific ticker.
        Applies slippage and commission assumptions.
        """
        log.info(f"Starting backtest for {ticker} from {start_date} to {end_date}...")

        # 1. Fetch historical data
        df_htf = self.data_loader._fetch_data_with_retry(ticker, "1d", "5y")
        df_ltf = self.data_loader._fetch_data_with_retry(ticker, "1h", "730d") # yfinance limit for 1h is usually 730d

        if df_htf.empty or df_ltf.empty:
            log.warning(f"Insufficient data for backtest: {ticker}")
            return pd.DataFrame()

        # 2. Add features and align MTF
        aligned_df = align_mtf_data(df_htf, df_ltf)

        if aligned_df.empty:
            return pd.DataFrame()

        # Filter dates
        aligned_df = aligned_df.loc[start_date:end_date]

        # 3. Simulate Trades
        trades = []
        open_trade = None

        for index, row in aligned_df.iterrows():
            # Check for exits if open
            if open_trade:
                exit_price = 0
                reason = ""
                # Simplistic SL/TP check on High/Low
                if open_trade['direction'] == 'Long':
                    if row['Low'] <= open_trade['sl']:
                        exit_price = open_trade['sl']
                        reason = "SL"
                    elif row['High'] >= open_trade['tp']:
                        exit_price = open_trade['tp']
                        reason = "TP"
                elif open_trade['direction'] == 'Short':
                    if row['High'] >= open_trade['sl']:
                        exit_price = open_trade['sl']
                        reason = "SL"
                    elif row['Low'] <= open_trade['tp']:
                        exit_price = open_trade['tp']
                        reason = "TP"

                if exit_price > 0:
                    # Apply Slippage on Exit
                    exit_price = exit_price * (0.9995 if open_trade['direction'] == 'Long' else 1.0005)

                    pnl = (exit_price - open_trade['entry_price']) * open_trade['size'] if open_trade['direction'] == 'Long' else (open_trade['entry_price'] - exit_price) * open_trade['size']

                    open_trade['exit_time'] = index
                    open_trade['exit_price'] = exit_price
                    open_trade['pnl'] = pnl
                    open_trade['reason'] = reason
                    trades.append(open_trade)
                    open_trade = None
                    continue # Skip entry logic on exit bar

            # Check for entries if flat
            if not open_trade:
                # Need to pass historical slice ending at current index to strategy
                hist_slice = aligned_df.loc[:index]
                if len(hist_slice) < 200: continue # Need warmup

                signal = check_entry_signal(hist_slice, ticker)
                if signal:
                    # Apply Slippage on Entry (0.1% total cost assumed for backtest simplicity)
                    entry_price = signal['entry_price'] * (1.001 if signal['direction'] == 'Long' else 0.999)

                    # Calculate position size (fixed risk % for simple backtest)
                    risk_pct = 0.02
                    risk_amount = INITIAL_CAPITAL * risk_pct
                    sl_dist = abs(entry_price - signal['sl'])
                    size = risk_amount / sl_dist if sl_dist > 0 else 0

                    open_trade = {
                        'trade_id': len(trades) + 1,
                        'ticker': ticker,
                        'direction': signal['direction'],
                        'entry_time': index,
                        'entry_price': entry_price,
                        'sl': signal['sl'],
                        'tp': signal['tp'],
                        'size': size,
                        'status': 'Closed', # Will be appended when closed
                        'pnl': 0
                    }

        return pd.DataFrame(trades)

    def calculate_metrics(self, trades_df: pd.DataFrame) -> Dict:
        """Calculates professional Quant metrics from backtest results."""
        if trades_df.empty: return {}

        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        net_pnl = gross_profit - gross_loss

        # Drawdown calculation
        trades_df['cumulative_pnl'] = trades_df['pnl'].cumsum()
        trades_df['equity'] = INITIAL_CAPITAL + trades_df['cumulative_pnl']
        trades_df['peak'] = trades_df['equity'].cummax()
        trades_df['drawdown'] = (trades_df['equity'] - trades_df['peak']) / trades_df['peak']
        max_drawdown = trades_df['drawdown'].min()

        return {
            'Total Trades': total_trades,
            'Net PnL': net_pnl,
            'Win Rate': win_rate,
            'Profit Factor': profit_factor,
            'Max Drawdown': max_drawdown
        }

    def grid_search_optimization(self, ticker: str, params: List[Dict]) -> pd.DataFrame:
        """
        Runs simple parameter optimization.
        params: List of dicts specifying indicator lengths, etc.
        (Placeholder for CPU-friendly optimization logic).
        """
        results = []
        for param_set in params:
            # Inject params into strategy/features (Requires refactoring features.py to accept params)
            # Run backtest
            # metrics = self.calculate_metrics(trades_df)
            # results.append({**param_set, **metrics})
            pass
        return pd.DataFrame(results)
