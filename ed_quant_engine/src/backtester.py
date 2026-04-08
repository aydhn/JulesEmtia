import pandas as pd
import numpy as np
from src.strategy import generate_signals
from src.config import get_spread

def run_vectorized_backtest(df: pd.DataFrame, ticker: str, initial_balance=10000.0) -> dict:
    """
    Simplified fast iterative backtest simulating the strategy rules with slippage and spread.
    """
    balance = initial_balance
    trades = []

    in_position = False
    entry_price = 0
    sl_price = 0
    tp_price = 0
    direction = ""
    pos_size = 0

    # We iterate manually to accurately simulate trailing stops and SL/TP hits.
    # Vectorized is hard for path-dependent logic (trailing stops).

    for i in range(1, len(df)):
        # Provide history up to current point to strategy
        current_slice = df.iloc[:i]

        if not in_position:
            # Look for signals
            signal = generate_signals(current_slice, ticker, balance)
            if signal:
                in_position = True
                direction = signal['direction']
                spread = get_spread(ticker)
                slippage = 0.0005

                raw_entry = signal['entry_price']
                if direction == 'Long':
                    entry_price = raw_entry + (spread/2) + slippage
                else:
                    entry_price = raw_entry - (spread/2) - slippage

                sl_price = signal['sl_price']
                tp_price = signal['tp_price']
                pos_size = signal['position_size']
        else:
            # Manage open position
            current_price = df['Close'].iloc[i]
            high = df['High'].iloc[i]
            low = df['Low'].iloc[i]
            atr = df['ATR_14'].iloc[i-1] if 'ATR_14' in df.columns else current_price * 0.01
            spread = get_spread(ticker)
            slippage = 0.0005

            exit_price = 0
            closed = False

            if direction == 'Long':
                if low <= sl_price:
                    exit_price = sl_price - (spread/2) - slippage
                    closed = True
                elif high >= tp_price:
                    exit_price = tp_price - (spread/2) - slippage
                    closed = True
                else:
                    # Trailing logic
                    if current_price >= entry_price + atr:
                        sl_price = max(sl_price, current_price - 1.5 * atr)
            else:
                if high >= sl_price:
                    exit_price = sl_price + (spread/2) + slippage
                    closed = True
                elif low <= tp_price:
                    exit_price = tp_price + (spread/2) + slippage
                    closed = True
                else:
                    if current_price <= entry_price - atr:
                        sl_price = min(sl_price, current_price + 1.5 * atr)

            if closed:
                if direction == 'Long':
                    pnl = (exit_price - entry_price) * pos_size
                else:
                    pnl = (entry_price - exit_price) * pos_size

                balance += pnl
                trades.append({
                    "ticker": ticker,
                    "direction": direction,
                    "pnl": pnl,
                    "pnl_pct": pnl / balance
                })
                in_position = False

    return {"final_balance": balance, "trades": trades}
