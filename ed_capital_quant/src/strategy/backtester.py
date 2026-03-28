import pandas as pd
import numpy as np
from src.core.logger import logger
from src.core.config import INITIAL_CAPITAL
from src.execution.costs import ExecutionModel
from src.strategy.rules import TradingRules

class Backtester:
    def __init__(self, data: pd.DataFrame, initial_capital: float = INITIAL_CAPITAL):
        self.data = data
        self.initial_capital = initial_capital

    def run_backtest(self, use_execution_costs: bool = True) -> dict:
        """
        Runs a vectorized backtest over the provided DataFrame.
        """
        logger.info("Running Backtest...")
        trades = []
        open_trade = None

        # We need a copy to iterate or vectorize safely
        df = self.data.copy()

        for i in range(1, len(df)):
            current_row = df.iloc[i]
            prev_row = df.iloc[i-1]

            # Simple simulation: If we have an open trade, check if it hits TP/SL
            if open_trade:
                hit = False
                current_price = current_row['Close']

                if open_trade['direction'] == 'Long':
                    if current_row['Low'] <= open_trade['sl']:
                        exit_price = open_trade['sl']
                        hit = True
                    elif current_row['High'] >= open_trade['tp']:
                        exit_price = open_trade['tp']
                        hit = True
                else:
                    if current_row['High'] >= open_trade['sl']:
                        exit_price = open_trade['sl']
                        hit = True
                    elif current_row['Low'] <= open_trade['tp']:
                        exit_price = open_trade['tp']
                        hit = True

                if hit:
                    if use_execution_costs:
                        avg_atr = df['ATR_14'].mean()
                        exit_price = ExecutionModel.get_execution_price(open_trade['ticker'], exit_price, "Short" if open_trade['direction'] == "Long" else "Long", current_row.get('ATR_14', 0), avg_atr)

                    pnl = ExecutionModel.calculate_net_pnl(open_trade['direction'], open_trade['entry_price'], exit_price, open_trade['size'])
                    open_trade['exit_price'] = exit_price
                    open_trade['pnl'] = pnl
                    open_trade['exit_time'] = current_row.name
                    trades.append(open_trade)
                    open_trade = None
                else:
                    # Trailing Stop
                    new_sl = TradingRules.calculate_trailing_stop(open_trade['direction'], current_price, open_trade['sl'], open_trade['entry_price'], current_row.get('ATR_14', 0) * 1.5)
                    open_trade['sl'] = new_sl

            # If no open trade, check for signals
            if not open_trade:
                # We need to simulate the signal generation.
                # For a true backtest, we would pass a slice of the dataframe up to i.
                # Here we mock it by passing a 2-row dataframe.
                slice_df = df.iloc[i-1:i+1]
                signal_data = TradingRules.generate_signal(slice_df)

                if signal_data['signal'] != 0:
                    direction = signal_data['direction']
                    entry_price = current_row['Close']

                    if use_execution_costs:
                        avg_atr = df['ATR_14'].mean()
                        entry_price = ExecutionModel.get_execution_price("MOCK_TICKER", entry_price, direction, current_row.get('ATR_14', 0), avg_atr)

                    # Calculate position size (mocking 2% risk)
                    risk_amount = self.initial_capital * 0.02
                    atr = signal_data['atr']
                    size = risk_amount / (1.5 * atr) if atr > 0 else 0

                    if size > 0:
                        open_trade = {
                            'ticker': "MOCK_TICKER",
                            'direction': direction,
                            'entry_price': entry_price,
                            'sl': signal_data['sl'],
                            'tp': signal_data['tp'],
                            'size': size,
                            'entry_time': current_row.name
                        }

        return self._calculate_metrics(trades)

    def _calculate_metrics(self, trades: list) -> dict:
        if not trades:
            return {"total_pnl": 0, "win_rate": 0, "profit_factor": 0, "trades": 0}

        df_trades = pd.DataFrame(trades)
        total_pnl = df_trades['pnl'].sum()
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]

        win_rate = len(wins) / len(df_trades) if len(df_trades) > 0 else 0
        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        return {
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "trades": len(df_trades)
        }
