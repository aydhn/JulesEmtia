import pandas as pd
import numpy as np
from core.logger import logger

class WalkForwardOptimizer:
    def __init__(self, data: pd.DataFrame, initial_capital=10000.0):
        self.data = data
        self.initial_capital = initial_capital

    def optimize(self, strategy_func, param_grid):
        """
        Runs a simplified rolling window optimization.
        - Train on 70% of data (In-Sample)
        - Test on next 30% of data (Out-of-Sample)

        Evaluates parameter robustness and Walk-Forward Efficiency (WFE).
        """
        logger.info("Walk-Forward Optimizer başlatılıyor...")

        total_len = len(self.data)
        if total_len < 200:
            logger.warning("Veri seti WFO için çok küçük.")
            return {"WFE": 0, "Status": "Insufficient Data"}

        is_size = int(total_len * 0.7)

        is_data = self.data.iloc[:is_size]
        oos_data = self.data.iloc[is_size:]

        # In a real scenario, this would loop over param_grid,
        # apply strategy_func with those parameters to IS data,
        # and measure PnL to pick the best params.

        # Here we simulate evaluating the current strategy's efficiency on historical vs recent data
        # Assume strategy_func returns a DataFrame of trades or PnL array

        is_trades = strategy_func(is_data)
        oos_trades = strategy_func(oos_data)

        if len(is_trades) == 0 or len(oos_trades) == 0:
            return {"WFE": 0, "Status": "No Trades"}

        # PnL Annualized = Total PnL / Years
        # For simplicity, calculate return on capital
        is_return = is_trades['pnl'].sum() / self.initial_capital
        oos_return = oos_trades['pnl'].sum() / self.initial_capital

        # Prevent division by zero or negative IS return
        if is_return <= 0:
            wfe = 0
        else:
            wfe = oos_return / is_return

        status = "Robust" if wfe > 0.5 else "Overfitted"
        logger.info(f"Walk-Forward Sonucu: IS=%{is_return*100:.2f}, OOS=%{oos_return*100:.2f}, WFE={wfe:.2f} -> {status}")

        return {
            "IS_Return": is_return,
            "OOS_Return": oos_return,
            "WFE": wfe,
            "Status": status
        }
