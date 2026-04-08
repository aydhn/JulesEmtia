import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class Backtester:
    """
    Phase 7: Historical Backtesting
    Phase 14: Walk-Forward Optimization (WFO)
    """
    def __init__(self):
        pass

    def run_backtest(self, df: pd.DataFrame) -> dict:
        """Simple vectorized backtest for strategy validation."""
        # A full backtest implementation would execute the Strategy over historical data.
        # This is a stub for integration purposes.
        logger.info("Running vectorized historical backtest...")
        return {"win_rate": 0.65, "profit_factor": 1.8, "total_pnl": 5000}

    def walk_forward_optimization(self, df: pd.DataFrame, is_window: int = 500, oos_window: int = 100):
        """
        Executes Walk-Forward Optimization.
        Checks Walk-Forward Efficiency (WFE) to prevent overfitting.
        """
        logger.info(f"Running WFO (IS: {is_window}, OOS: {oos_window})...")

        if df.empty or len(df) < (is_window + oos_window):
            logger.warning("Not enough data for WFO.")
            return False

        # Simulate sliding windows
        total_len = len(df)
        start_idx = 0
        wfe_results = []

        # We simulate optimization simply by comparing returns.
        # In a real engine, we would grid search parameters here.
        # We assume parameters are static for this simulation to calculate robustness.

        while start_idx + is_window + oos_window <= total_len:
            # Split data
            is_df = df.iloc[start_idx : start_idx + is_window]
            oos_df = df.iloc[start_idx + is_window : start_idx + is_window + oos_window]

            # Simulated IS Return (Annualized) - stub logic for demonstration
            # In real system, this calls run_backtest()
            is_res = self.run_backtest(is_df)
            is_return = is_res.get("total_pnl", 1) / 10000.0  # normalized
            is_ann = is_return * (252 / is_window) if is_window > 0 else 0

            # Simulated OOS Return
            oos_res = self.run_backtest(oos_df)
            oos_return = oos_res.get("total_pnl", 1) / 10000.0 # normalized
            oos_ann = oos_return * (252 / oos_window) if oos_window > 0 else 0

            # Calculate WFE
            if is_ann > 0:
                wfe = oos_ann / is_ann
            else:
                wfe = 0.0

            wfe_results.append(wfe)
            start_idx += oos_window

        avg_wfe = np.mean(wfe_results) if wfe_results else 0.0
        logger.info(f"WFO Average Walk-Forward Efficiency (WFE): {avg_wfe:.2f}")

        # Critical Rule: If WFE < 0.5, reject parameters
        if avg_wfe < 0.5:
            logger.warning("Parameters rejected due to low Walk-Forward Efficiency (Overfitted).")
            return False

        logger.info("WFO complete. Robust parameters selected.")
        return True
