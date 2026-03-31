import pandas as pd
import numpy as np
from typing import Dict, Any, List
from strategy import QuantStrategy
from execution_model import ExecutionSimulator
from logger import logger

class VectorizedBacktester:
    """
    Phase 7: Historical Backtesting Engine
    Simulates strategy logic on historical data.
    Fast, iterative/vectorized approach without heavy external frameworks.
    Includes brutal realism: Spread & Slippage.
    """

    @classmethod
    def run_backtest(cls, ticker: str, daily_df: pd.DataFrame, hourly_df: pd.DataFrame) -> pd.DataFrame:
        """
        Runs a historical backtest for a single asset.
        Returns a DataFrame of executed trades.
        """
        if hourly_df.empty or daily_df.empty:
            return pd.DataFrame()

        trades = []
        is_open = False
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        direction = 0
        entry_time = None

        # We need a simulated account size to track PnL roughly
        account_size = 10000.0
        risk_pct = 0.02 # Constant risk for simple backtest

        # Iterate through hourly data (simulating time passing)
        # Start from index 50 to ensure indicators have enough lookback
        for i in range(50, len(hourly_df)):
            current_idx = hourly_df.index[i]
            current_row = hourly_df.iloc[i]

            # Find the corresponding daily row (last closed daily candle BEFORE current hour)
            # This prevents lookahead bias in backtesting
            past_daily = daily_df[daily_df.index < current_idx]
            if past_daily.empty:
                continue

            current_daily_row = past_daily.iloc[-1]

            # 1. Check Open Trades
            if is_open:
                current_price = current_row['Close']
                exit_price = 0.0
                reason = ""

                # Check SL/TP
                if direction == 1: # Long
                    if current_row['Low'] <= sl_price:
                        # Slippage applied on SL exit
                        exit_price = ExecutionSimulator.execute_trade_price(ticker, sl_price, -1, pd.Series([current_row['ATR_14']]))
                        reason = "SL Hit"
                    elif current_row['High'] >= tp_price:
                        exit_price = ExecutionSimulator.execute_trade_price(ticker, tp_price, -1, pd.Series([current_row['ATR_14']]))
                        reason = "TP Hit"
                else: # Short
                    if current_row['High'] >= sl_price:
                        exit_price = ExecutionSimulator.execute_trade_price(ticker, sl_price, 1, pd.Series([current_row['ATR_14']]))
                        reason = "SL Hit"
                    elif current_row['Low'] <= tp_price:
                        exit_price = ExecutionSimulator.execute_trade_price(ticker, tp_price, 1, pd.Series([current_row['ATR_14']]))
                        reason = "TP Hit"

                # Close Trade
                if exit_price > 0:
                    # Calculate PnL
                    # Rough position sizing: Risk Amount / SL Distance
                    risk_amount = account_size * risk_pct
                    sl_dist = abs(entry_price - sl_price)
                    pos_size = risk_amount / sl_dist if sl_dist > 0 else 0

                    pnl = (exit_price - entry_price) * pos_size * direction
                    account_size += pnl # Compounding

                    trades.append({
                        'ticker': ticker,
                        'direction': 'Long' if direction == 1 else 'Short',
                        'entry_time': entry_time,
                        'exit_time': current_idx,
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'pnl': pnl,
                        'reason': reason
                    })
                    is_open = False
                continue # Skip looking for new entries while in a trade (Simple backtest logic)

            # 2. Look for New Signals
            # Create a mock slice of data up to this point to feed the strategy
            # To be efficient, we manually replicate the core Strategy confluence logic here
            # to avoid async overhead during millions of backtest iterations.

            # Master Veto (Daily)
            htf_trend = 0
            if len(past_daily) >= 2:
                prev_day = past_daily.iloc[-2]
                if prev_day['Close'] > prev_day['EMA_50'] and prev_day['MACD'] > 0:
                    htf_trend = 1
                elif prev_day['Close'] < prev_day['EMA_50'] and prev_day['MACD'] < 0:
                    htf_trend = -1

            if htf_trend == 0:
                continue

            # LTF Sniper Entry
            prev_hour = hourly_df.iloc[i-1]
            prev2_hour = hourly_df.iloc[i-2]

            signal_dir = 0
            if htf_trend == 1:
                if prev_hour['RSI_14'] < 30 and prev2_hour['RSI_14'] >= 30:
                    signal_dir = 1
                elif prev_hour['Low'] <= prev_hour['BBL_20_2.0']:
                    signal_dir = 1
            elif htf_trend == -1:
                if prev_hour['RSI_14'] > 70 and prev2_hour['RSI_14'] <= 70:
                    signal_dir = -1
                elif prev_hour['High'] >= prev_hour['BBU_20_2.0']:
                    signal_dir = -1

            if signal_dir != 0:
                # Open Trade
                raw_entry = current_row['Open']
                atr = prev_hour['ATR_14']

                # Apply Execution Costs
                exec_entry = ExecutionSimulator.execute_trade_price(ticker, raw_entry, signal_dir, pd.Series([atr]))

                if signal_dir == 1:
                    raw_sl = exec_entry - (1.5 * atr)
                    raw_tp = exec_entry + (3.0 * atr)
                    exec_sl = ExecutionSimulator.execute_trade_price(ticker, raw_sl, -1, pd.Series([atr]))
                    exec_tp = ExecutionSimulator.execute_trade_price(ticker, raw_tp, -1, pd.Series([atr]))
                else:
                    raw_sl = exec_entry + (1.5 * atr)
                    raw_tp = exec_entry - (3.0 * atr)
                    exec_sl = ExecutionSimulator.execute_trade_price(ticker, raw_sl, 1, pd.Series([atr]))
                    exec_tp = ExecutionSimulator.execute_trade_price(ticker, raw_tp, 1, pd.Series([atr]))

                is_open = True
                direction = signal_dir
                entry_price = exec_entry
                sl_price = exec_sl
                tp_price = exec_tp
                entry_time = current_idx

        return pd.DataFrame(trades)

    @classmethod
    def analyze_results(cls, trades_df: pd.DataFrame) -> dict:
        """Calculates Quant metrics for a backtest run."""
        if trades_df.empty:
            return {"Win Rate": 0, "Profit Factor": 0, "Total PnL": 0, "Trades": 0}

        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] <= 0]

        win_rate = len(wins) / len(trades_df)

        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

        total_pnl = trades_df['pnl'].sum()

        return {
            "Win Rate": win_rate,
            "Profit Factor": profit_factor,
            "Total PnL": total_pnl,
            "Trades": len(trades_df)
        }
