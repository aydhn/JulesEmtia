import pandas as pd
import numpy as np
from typing import Dict
from .logger import quant_logger
from .strategy import StrategyEngine

class Backtester:
    def __init__(self):
        self.results = []

    def run_vectorized(self, ticker: str, df: pd.DataFrame, slippage_pct: float = 0.001) -> dict:
        """
        Fast vectorized backtest. (Phase 7)
        """
        if df.empty or len(df) < 50: return {}

        # Simplified vector logic for fast testing
        df['Signal'] = 0

        # Long
        long_cond = (df.get('Close_HTF', df['Close']) > df.get('EMA_50_HTF', df['Close'])) & \
                    (df['Close'] > df.get('EMA_50', 0)) & \
                    ((df.get('RSI_14', 50) < 35) | (df['Close'] <= df.get('BBL_20_2.0', 0))) & \
                    (df.get('MACDh_12_26_9', 0) > 0)

        # Short
        short_cond = (df.get('Close_HTF', df['Close']) < df.get('EMA_50_HTF', 9999)) & \
                     (df['Close'] < df.get('EMA_50', 9999)) & \
                     ((df.get('RSI_14', 50) > 65) | (df['Close'] >= df.get('BBU_20_2.0', 9999))) & \
                     (df.get('MACDh_12_26_9', 0) < 0)

        df.loc[long_cond, 'Signal'] = 1
        df.loc[short_cond, 'Signal'] = -1

        # Shift signal to prevent lookahead
        df['Signal'] = df['Signal'].shift(1)

        # Calculate Returns
        df['Strategy_Return'] = df['Signal'] * df['Log_Return'] - slippage_pct * abs(df['Signal'].diff().fillna(0))

        cum_ret = np.exp(df['Strategy_Return'].cumsum())
        total_pnl = cum_ret.iloc[-1] - 1.0 if len(cum_ret) > 0 else 0.0

        # Win Rate approx
        wins = len(df[df['Strategy_Return'] > 0])
        losses = len(df[df['Strategy_Return'] < 0])
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0

        return {'ticker': ticker, 'pnl': total_pnl, 'win_rate': win_rate}
