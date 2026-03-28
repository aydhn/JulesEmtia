import pandas as pd
from quant.strategy import StrategyEngine
from execution.execution_model import calculate_execution_price

class Backtester:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 10000.0):
        self.df = df
        self.initial_capital = initial_capital

    def run_backtest(self):
        # Vektörel ve iteratif basit bir backtest motoru
        capital = self.initial_capital
        trades = []
        open_trade = None

        for idx, row in self.df.iterrows():
            if open_trade is None:
                # Sinyal kontrol
                signal = StrategyEngine.check_signal(self.df.loc[:idx])
                if signal:
                    # Fake atr, normalde önceden hesaplanmalı
                    atr = row.get('ATRr_14', 1.0)
                    exec_price = calculate_execution_price(row['Close'], atr, "METALS", signal)
                    sl, tp = StrategyEngine.calculate_dynamic_risk(exec_price, atr, signal)

                    open_trade = {
                        'entry_time': idx,
                        'entry_price': exec_price,
                        'direction': signal,
                        'sl': sl,
                        'tp': tp,
                        'size': (capital * 0.02) / abs(exec_price - sl) if abs(exec_price - sl) > 0 else 0
                    }
            else:
                # Çıkış kontrolü
                hit_sl = (open_trade['direction'] == "Long" and row['Low'] <= open_trade['sl']) or \
                         (open_trade['direction'] == "Short" and row['High'] >= open_trade['sl'])
                hit_tp = (open_trade['direction'] == "Long" and row['High'] >= open_trade['tp']) or \
                         (open_trade['direction'] == "Short" and row['Low'] <= open_trade['tp'])

                if hit_sl or hit_tp:
                    exit_price = open_trade['sl'] if hit_sl else open_trade['tp']
                    # Slippage eklenebilir
                    pnl = (exit_price - open_trade['entry_price']) * open_trade['size'] if open_trade['direction'] == "Long" else (open_trade['entry_price'] - exit_price) * open_trade['size']
                    capital += pnl
                    trades.append({
                        'entry_time': open_trade['entry_time'],
                        'exit_time': idx,
                        'pnl': pnl,
                        'capital': capital
                    })
                    open_trade = None
                else:
                    # İzleyen stop
                    atr = row.get('ATRr_14', 1.0)
                    open_trade['sl'] = StrategyEngine.manage_trailing_stop({'sl_price': open_trade['sl'], 'entry_price': open_trade['entry_price'], 'direction': open_trade['direction']}, row['Close'], atr)

        return pd.DataFrame(trades)
