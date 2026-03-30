import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from logger import log
from features import add_features
from data_loader import UNIVERSE, fetch_mtf_data, align_mtf_data

class VectorizedBacktester:
    """
    Vectorized Backtest Engine (Phase 7).
    Executes Strategy logic over historical data simulating slippage/commission.
    Optimized for CPU usage avoiding python loops where possible.
    """
    def __init__(self, initial_capital: float = 10000.0, commission_pct: float = 0.0005, slippage_pct: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def run_backtest(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """
        Runs a vectorized backtest on the given DataFrame.
        Returns a DataFrame of trades.
        """
        if df.empty or len(df) < 50:
            return pd.DataFrame()

        df = df.copy()

        # Generate Signals based on Strategy Logic (Phase 4 / 16)
        # 1: Long, -1: Short, 0: Neutral

        # Long Conditions
        long_cond = (
            (df['close'] > df['EMA_50']) &
            (df['RSI_14'] > 30) & (df['RSI_14'].shift(1) <= 30) &
            (df['MACD_Hist'] > 0)
        )

        # Short Conditions
        short_cond = (
            (df['close'] < df['EMA_50']) &
            (df['RSI_14'] < 70) & (df['RSI_14'].shift(1) >= 70) &
            (df['MACD_Hist'] < 0)
        )

        df['Signal'] = np.where(long_cond, 1, np.where(short_cond, -1, 0))

        # Shift signal to avoid lookahead bias
        df['Signal'] = df['Signal'].shift(1)

        trades = []
        in_position = 0
        entry_price = 0.0
        sl_price = 0.0
        tp_price = 0.0
        direction = ""

        # Iterative fallback for path-dependent logic (Trailing Stops / TP)
        # Numba could optimize this, but sticking to pure python for zero dependencies
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            signal = row['Signal']

            if in_position == 0 and signal != 0:
                # Enter Position
                direction = "Long" if signal == 1 else "Short"
                entry_price = row['open'] # Assume entry on next open

                # Dynamic ATR SL/TP
                atr = prev_row['ATR_14']
                if pd.isna(atr) or atr == 0: continue

                # Apply Slippage
                entry_price = entry_price * (1 + self.slippage_pct) if direction == "Long" else entry_price * (1 - self.slippage_pct)

                if direction == "Long":
                    sl_price = entry_price - (1.5 * atr)
                    tp_price = entry_price + (3.0 * atr)
                else:
                    sl_price = entry_price + (1.5 * atr)
                    tp_price = entry_price - (3.0 * atr)

                in_position = signal

            elif in_position != 0:
                # Check Exit Conditions
                current_low = row['low']
                current_high = row['high']

                exit_price = 0.0
                reason = ""

                if direction == "Long":
                    if current_low <= sl_price:
                        exit_price = sl_price
                        reason = "SL"
                    elif current_high >= tp_price:
                        exit_price = tp_price
                        reason = "TP"
                else: # Short
                    if current_high >= sl_price:
                        exit_price = sl_price
                        reason = "SL"
                    elif current_low <= tp_price:
                        exit_price = tp_price
                        reason = "TP"

                if reason:
                    # Apply Slippage on Exit
                    exit_price = exit_price * (1 - self.slippage_pct) if direction == "Long" else exit_price * (1 + self.slippage_pct)

                    # Calculate PnL (%)
                    if direction == "Long":
                        pnl_pct = (exit_price - entry_price) / entry_price
                    else:
                        pnl_pct = (entry_price - exit_price) / entry_price

                    pnl_pct -= self.commission_pct * 2 # Round trip commission

                    trades.append({
                        "ticker": ticker,
                        "entry_time": df.index[i-1], # approximate
                        "exit_time": df.index[i],
                        "direction": direction,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_pct": pnl_pct,
                        "reason": reason
                    })

                    in_position = 0

        return pd.DataFrame(trades)

