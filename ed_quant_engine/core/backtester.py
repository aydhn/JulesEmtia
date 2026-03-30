import pandas as pd
import numpy as np
import yfinance as yf
from core.quant_logic import Strategy
from system.logger import log

class Backtester:
    def __init__(self, ticker, period="5y"):
        self.ticker = ticker
        self.period = period
        self.df = None

    def fetch_data(self):
        log.info(f"Fetching {self.period} data for {self.ticker} Backtest...")
        df_1d = yf.download(self.ticker, period=self.period, interval="1d", progress=False)

        # Simulating 1H precision on daily data for speed/limitations.
        # In a real WFO, you'd fetch massive 1H chunks and merge.
        if df_1d.empty:
            log.warning(f"No data for {self.ticker}")
            return False

        self.df = Strategy.add_features(df_1d.ffill())
        return not self.df.empty

    def run_backtest(self, rsi_ob=70, rsi_os=30, ema_trend=50):
        """Phase 7: Vectorized historical backtest simulation"""
        if self.df is None or self.df.empty:
            return None

        df = self.df.copy()
        df['Prev_Close'] = df['Close'].shift(1)
        df[f'Prev_EMA_{ema_trend}'] = df[f'EMA_{ema_trend}'].shift(1) if f'EMA_{ema_trend}' in df.columns else df['EMA_50'].shift(1)
        df['Prev_RSI'] = df['RSI_14'].shift(1)
        df['Prev_MACDh'] = df['MACD_Hist'].shift(1)
        df['Prev_BBL'] = df['BB_LOWER'].shift(1)
        df['Prev_BBU'] = df['BB_UPPER'].shift(1)
        df['Prev_ATR'] = df['ATR'].shift(1)

        # Long
        buy_cond = (df['Prev_Close'] > df[f'Prev_EMA_{ema_trend}']) & \
                   ((df['Prev_RSI'] < rsi_os) | (df['Prev_Close'] <= df['Prev_BBL'])) & \
                   (df['Prev_MACDh'] > 0)

        # Short
        sell_cond = (df['Prev_Close'] < df[f'Prev_EMA_{ema_trend}']) & \
                    ((df['Prev_RSI'] > rsi_ob) | (df['Prev_Close'] >= df['Prev_BBU'])) & \
                    (df['Prev_MACDh'] < 0)

        df['Signal'] = np.where(buy_cond, 1, np.where(sell_cond, -1, 0))

        # Execution Simulator (Vectorized approximations)
        trades = []
        open_pos = 0

        for i, row in df.iterrows():
            if open_pos == 0 and row['Signal'] != 0:
                open_pos = row['Signal']
                entry = row['Close']
                atr = row['Prev_ATR']
                sl = entry - (1.5*atr) if open_pos == 1 else entry + (1.5*atr)
                tp = entry + (3.0*atr) if open_pos == 1 else entry - (3.0*atr)

                trades.append({
                    'entry_date': i, 'dir': open_pos, 'entry': entry,
                    'sl': sl, 'tp': tp, 'atr': atr, 'status': 'OPEN'
                })
            elif open_pos != 0:
                curr_trade = trades[-1]
                p = row['Close']
                # SL / TP Hit Check
                if (curr_trade['dir'] == 1 and (p <= curr_trade['sl'] or p >= curr_trade['tp'])) or \
                   (curr_trade['dir'] == -1 and (p >= curr_trade['sl'] or p <= curr_trade['tp'])):

                    exit_p = curr_trade['sl'] if (curr_trade['dir']==1 and p<=curr_trade['sl']) or (curr_trade['dir']==-1 and p>=curr_trade['sl']) else curr_trade['tp']

                    # Slippage 0.1% + Commission 0.05%
                    slip_cost = exit_p * 0.0015

                    pnl_raw = (exit_p - curr_trade['entry']) if curr_trade['dir'] == 1 else (curr_trade['entry'] - exit_p)
                    pnl_net = pnl_raw - slip_cost - (curr_trade['entry']*0.0015)

                    curr_trade['exit_date'] = i
                    curr_trade['exit'] = exit_p
                    curr_trade['pnl'] = pnl_net
                    curr_trade['status'] = 'CLOSED'
                    open_pos = 0

        res = [t for t in trades if t['status'] == 'CLOSED']
        if not res: return 0.0, 0.0

        wins = [t for t in res if t['pnl'] > 0]
        win_rate = len(wins) / len(res)
        net_profit = sum(t['pnl'] for t in res)
        return net_profit, win_rate

    def walk_forward_optimization(self):
        """Phase 14: OOS / IS testing"""
        if self.df is None or len(self.df) < 500:
            return "Not enough data for WFO"

        splits = np.array_split(self.df, 3) # 3 windows

        results = []
        for i in range(len(splits) - 1):
            is_df = splits[i]
            oos_df = splits[i+1]

            # Simple grid search on IS
            best_net = -9999
            best_params = None

            for r_os in [25, 30]:
                for r_ob in [70, 75]:
                    self.df = is_df
                    net, wr = self.run_backtest(rsi_ob=r_ob, rsi_os=r_os)
                    if net > best_net:
                        best_net = net
                        best_params = (r_ob, r_os)

            # Test on OOS
            self.df = oos_df
            if best_params:
                oos_net, oos_wr = self.run_backtest(rsi_ob=best_params[0], rsi_os=best_params[1])

                # WFE
                wfe = (oos_net / max(1, best_net)) * 100
                status = "Robust" if wfe > 50 else "Overfitted"

                results.append({
                    'window': i, 'params': best_params,
                    'IS_Net': best_net, 'OOS_Net': oos_net,
                    'WFE_%': wfe, 'Status': status
                })

        self.fetch_data() # restore full df
        return pd.DataFrame(results)

if __name__ == "__main__":
    bt = Backtester("GC=F")
    if bt.fetch_data():
        net, wr = bt.run_backtest()
        print(f"Backtest Net: {net:.2f}, Win Rate: {wr*100:.1f}%")
        print("\nWFO Results:")
        print(bt.walk_forward_optimization())
