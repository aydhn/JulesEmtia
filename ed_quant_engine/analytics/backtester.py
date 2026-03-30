import pandas as pd
import numpy as np

def run_backtest(df: pd.DataFrame, initial_balance=10000.0, slippage_pct=0.001):
    balance = initial_balance
    trades = []

    for i in range(1, len(df)):
        signal = df['Signal'].iloc[i]

        if signal == 1:
            entry = df['Close'].iloc[i] * (1 + slippage_pct)
            sl = entry - (df['ATR_14'].iloc[i] * 1.5)
            tp = entry + (df['ATR_14'].iloc[i] * 3.0)

            # Simulate holding until TP/SL
            for j in range(i+1, len(df)):
                low = df['Low'].iloc[j]
                high = df['High'].iloc[j]
                if low <= sl:
                    pnl = (sl - entry) / entry
                    trades.append({'PnL': pnl, 'Exit_Type': 'SL'})
                    balance *= (1 + pnl)
                    break
                elif high >= tp:
                    pnl = (tp - entry) / entry
                    trades.append({'PnL': pnl, 'Exit_Type': 'TP'})
                    balance *= (1 + pnl)
                    break

        elif signal == -1:
            entry = df['Close'].iloc[i] * (1 - slippage_pct)
            sl = entry + (df['ATR_14'].iloc[i] * 1.5)
            tp = entry - (df['ATR_14'].iloc[i] * 3.0)

            for j in range(i+1, len(df)):
                high = df['High'].iloc[j]
                low = df['Low'].iloc[j]
                if high >= sl:
                    pnl = (entry - sl) / entry
                    trades.append({'PnL': pnl, 'Exit_Type': 'SL'})
                    balance *= (1 + pnl)
                    break
                elif low <= tp:
                    pnl = (entry - tp) / entry
                    trades.append({'PnL': pnl, 'Exit_Type': 'TP'})
                    balance *= (1 + pnl)
                    break

    results = pd.DataFrame(trades)
    if not results.empty:
        win_rate = len(results[results['PnL'] > 0]) / len(results)
        gross_profit = results[results['PnL'] > 0]['PnL'].sum()
        gross_loss = abs(results[results['PnL'] < 0]['PnL'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
        max_drawdown = (results['PnL'].cumsum().cummax() - results['PnL'].cumsum()).max()

        return {
            'Win_Rate': win_rate,
            'Profit_Factor': profit_factor,
            'Max_Drawdown': max_drawdown,
            'Total_Trades': len(results),
            'Final_Balance': balance
        }
    return None
