import pandas as pd
import numpy as np
from src.core.logger import logger
from src.strategy.backtester import Backtester

class WalkForwardOptimizer:
    def __init__(self, data: pd.DataFrame):
        self.data = data

    def run_wfo(self, is_window: int = 252*2, oos_window: int = 252//2) -> dict:
        """
        Runs Walk-Forward Optimization.
        is_window: In-Sample window size (e.g., 2 years)
        oos_window: Out-Of-Sample window size (e.g., 6 months)
        """
        logger.info("Starting Walk-Forward Optimization...")
        total_rows = len(self.data)

        if total_rows < is_window + oos_window:
            logger.warning("Not enough data for WFO.")
            return {}

        results = []
        start_idx = 0

        while start_idx + is_window + oos_window <= total_rows:
            is_data = self.data.iloc[start_idx : start_idx + is_window]
            oos_data = self.data.iloc[start_idx + is_window : start_idx + is_window + oos_window]

            # In-Sample Backtest
            is_bt = Backtester(is_data)
            is_metrics = is_bt.run_backtest()

            # Out-Of-Sample Backtest (using same parameters implicitly)
            oos_bt = Backtester(oos_data)
            oos_metrics = oos_bt.run_backtest()

            # Walk-Forward Efficiency (Annualized)
            is_annual_pnl = is_metrics['total_pnl'] * (252 / is_window)
            oos_annual_pnl = oos_metrics['total_pnl'] * (252 / oos_window)

            wfe = oos_annual_pnl / is_annual_pnl if is_annual_pnl > 0 else 0

            results.append({
                "period_start": is_data.index[0],
                "is_pnl": is_metrics['total_pnl'],
                "oos_pnl": oos_metrics['total_pnl'],
                "wfe": wfe
            })

            start_idx += oos_window

        df_results = pd.DataFrame(results)
        avg_wfe = df_results['wfe'].mean()

        logger.info(f"WFO Completed. Average WFE: {avg_wfe:.2f}")
        return {
            "avg_wfe": avg_wfe,
            "results": df_results.to_dict(orient="records")
        }
