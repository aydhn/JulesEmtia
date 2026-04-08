import pandas as pd
import numpy as np
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class Backtester:
    """
    Phase 7: Historical Backtesting Engine
    Executes Strategy across historical data accurately including slippage/commission.
    """
    def __init__(self, initial_capital: float = 10000.0, slippage_pct: float = 0.0010, comm_pct: float = 0.0005):
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct
        self.comm_pct = comm_pct

    def run_backtest(self, mtf_df: pd.DataFrame, strategy_func, atr_sl_mult=1.5, atr_tp_mult=3.0) -> Dict:
        """
        Iterative backtest mimicking live execution to extract realistic PnL.
        Phase 7 constraints: 0.1% slippage, 0.05% commission.
        """
        logger.info("Running realistic historical backtest...")
        if mtf_df is None or mtf_df.empty or len(mtf_df) < 50:
            return {"total_trades": 0, "win_rate": 0, "profit_factor": 0, "total_pnl": 0, "max_dd": 0}

        balance = self.initial_capital
        peak_balance = balance
        max_dd = 0.0

        trades = []
        open_trade = None

        # Iterate over DataFrame to simulate time
        for i in range(2, len(mtf_df)):
            current_idx = mtf_df.index[i]
            current_row = mtf_df.iloc[i]

            # To avoid lookahead bias, signals must be generated using data UP TO previous candle
            # Because strategy.generate_signal expects the whole dataframe up to point of evaluation,
            # we slice up to i. The strategy itself looks at mtf_df.iloc[-2] for signals (the completed candle).
            slice_df = mtf_df.iloc[:i+1]

            # 1. Manage Open Trade
            if open_trade is not None:
                curr_price = float(current_row['Close'])
                high = float(current_row['High'])
                low = float(current_row['Low'])

                # Check hits
                sl_hit = False
                tp_hit = False
                exit_price = 0.0

                if open_trade['dir'] == "LONG":
                    if low <= open_trade['sl']:
                        sl_hit = True
                        exit_price = open_trade['sl']
                    elif high >= open_trade['tp']:
                        tp_hit = True
                        exit_price = open_trade['tp']
                else:
                    if high >= open_trade['sl']:
                        sl_hit = True
                        exit_price = open_trade['sl']
                    elif low <= open_trade['tp']:
                        tp_hit = True
                        exit_price = open_trade['tp']

                if sl_hit or tp_hit:
                    # Apply execution costs on exit
                    exit_price_net = exit_price * (1 - self.slippage_pct) if open_trade['dir'] == "LONG" else exit_price * (1 + self.slippage_pct)
                    gross_pnl = (exit_price_net - open_trade['entry']) * open_trade['size'] if open_trade['dir'] == "LONG" else (open_trade['entry'] - exit_price_net) * open_trade['size']
                    net_pnl = gross_pnl - (exit_price_net * open_trade['size'] * self.comm_pct)

                    balance += net_pnl
                    if balance > peak_balance:
                        peak_balance = balance
                    else:
                        dd = (peak_balance - balance) / peak_balance
                        if dd > max_dd:
                            max_dd = dd

                    trades.append(net_pnl)
                    open_trade = None
                    continue # Wait for next candle to open new trade

            # 2. Check for New Signals if no open trade
            if open_trade is None:
                signal = strategy_func(slice_df)
                if signal:
                    direction = signal['dir']
                    signal_price = float(signal['price'])
                    atr = float(signal['atr'])

                    # Apply execution costs on entry
                    entry_price = signal_price * (1 + self.slippage_pct) if direction == "LONG" else signal_price * (1 - self.slippage_pct)

                    # Position sizing (Assume 2% risk)
                    risk_amount = balance * 0.02
                    sl_dist = atr_sl_mult * atr
                    if sl_dist == 0: continue

                    size = risk_amount / sl_dist
                    comm_cost = entry_price * size * self.comm_pct
                    balance -= comm_cost # Deduct commission immediately

                    sl = entry_price - sl_dist if direction == "LONG" else entry_price + sl_dist
                    tp = entry_price + (atr_tp_mult * atr) if direction == "LONG" else entry_price - (atr_tp_mult * atr)

                    open_trade = {
                        "dir": direction,
                        "entry": entry_price,
                        "size": size,
                        "sl": sl,
                        "tp": tp
                    }

        # Calculate metrics
        total_trades = len(trades)
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]

        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 99.0
        total_pnl = balance - self.initial_capital

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "max_dd": max_dd
        }
