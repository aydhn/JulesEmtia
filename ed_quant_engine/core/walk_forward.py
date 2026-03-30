import pandas as pd
import numpy as np
from typing import Dict, Any, List

from .backtester import FastBacktester
from .infrastructure import logger

class WalkForwardOptimizer:
    """Phase 14: Walk-Forward Optimization Engine."""

    def __init__(self, df: pd.DataFrame, ticker: str, is_window_days: int = 730, oos_window_days: int = 180):
        self.df = df.copy()
        self.ticker = ticker
        self.is_window = is_window_days  # In-Sample (e.g., 2 years)
        self.oos_window = oos_window_days # Out-of-Sample (e.g., 6 months)

    def execute_wfo(self) -> Dict[str, Any]:
        """Runs rolling window optimization and computes WFE."""
        logger.info(f"Starting Walk-Forward Optimization for {self.ticker}")

        # Ensure index is datetime
        if not isinstance(self.df.index, pd.DatetimeIndex):
            self.df.index = pd.to_datetime(self.df.index)

        start_date = self.df.index.min()
        end_date = self.df.index.max()

        current_start = start_date

        total_is_pnl_annualized = 0.0
        total_oos_pnl_annualized = 0.0
        windows_completed = 0
        wfo_results = []

        while True:
            is_end = current_start + pd.Timedelta(days=self.is_window)
            oos_end = is_end + pd.Timedelta(days=self.oos_window)

            if oos_end > end_date:
                break

            is_df = self.df[(self.df.index >= current_start) & (self.df.index < is_end)]
            oos_df = self.df[(self.df.index >= is_end) & (self.df.index < oos_end)]

            if is_df.empty or oos_df.empty:
                current_start += pd.Timedelta(days=self.oos_window)
                continue

            # 1. Optimize on In-Sample
            bt_is = FastBacktester(is_df, self.ticker)
            opt_result = bt_is.grid_search_optimization()
            best_params = opt_result.get("best_params")
            is_metrics = opt_result.get("best_metrics", {})

            if not best_params:
                logger.warning(f"No viable parameters found for {self.ticker} in window {current_start.date()} to {is_end.date()}")
                current_start += pd.Timedelta(days=self.oos_window)
                continue

            # 2. Test on Out-of-Sample
            bt_oos = FastBacktester(oos_df, self.ticker)
            oos_result = bt_oos.run_backtest(**best_params)

            # 3. Calculate WFE (Walk-Forward Efficiency)
            # Annualize PnL
            is_years = self.is_window / 365.25
            oos_years = self.oos_window / 365.25

            is_ann_pnl = is_metrics.get("total_pnl", 0) / is_years if is_years > 0 else 0
            oos_ann_pnl = oos_result.get("total_pnl", 0) / oos_years if oos_years > 0 else 0

            wfe = oos_ann_pnl / is_ann_pnl if is_ann_pnl > 0 else 0

            logger.info(f"WFO Window [{is_end.date()} -> {oos_end.date()}]: IS PnL: {is_ann_pnl:.2%}, OOS PnL: {oos_ann_pnl:.2%}, WFE: {wfe:.2f}")

            wfo_results.append({
                "window_start": current_start,
                "window_end": oos_end,
                "best_params": best_params,
                "is_pnl": is_ann_pnl,
                "oos_pnl": oos_ann_pnl,
                "wfe": wfe
            })

            total_is_pnl_annualized += is_ann_pnl
            total_oos_pnl_annualized += oos_ann_pnl
            windows_completed += 1

            # Step forward
            current_start += pd.Timedelta(days=self.oos_window)

        avg_wfe = total_oos_pnl_annualized / total_is_pnl_annualized if total_is_pnl_annualized > 0 else 0

        # Robustness Check (Reject if WFE < 50%)
        is_robust = avg_wfe > 0.50

        logger.info(f"WFO Completed. Avg WFE: {avg_wfe:.2f}. Robust: {is_robust}")

        return {
            "robust": is_robust,
            "avg_wfe": avg_wfe,
            "windows": wfo_results
        }
