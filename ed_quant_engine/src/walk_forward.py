import pandas as pd
from .logger import quant_logger
from .backtester import Backtester

class WalkForwardOptimizer:
    def __init__(self):
        self.bt = Backtester()

    def optimize(self, df: pd.DataFrame, window_size: int = 252*2, step_size: int = 252//2) -> bool:
        """
        Phase 14: Walk Forward Optimization to prevent Curve Fitting.
        Returns True if Strategy is Robust (WFE > 50%).
        """
        if df.empty or len(df) < window_size + step_size:
            return False

        wfe_scores = []

        for start in range(0, len(df) - window_size - step_size, step_size):
            # In-Sample (IS)
            is_df = df.iloc[start : start + window_size].copy()
            is_res = self.bt.run_vectorized('WFO_TEST', is_df)

            # Out-of-Sample (OOS)
            oos_df = df.iloc[start + window_size : start + window_size + step_size].copy()
            oos_res = self.bt.run_vectorized('WFO_TEST', oos_df)

            is_pnl = is_res.get('pnl', 0)
            oos_pnl = oos_res.get('pnl', 0)

            if is_pnl > 0:
                # Annualize rough estimate
                wfe = (oos_pnl / (step_size/252)) / (is_pnl / (window_size/252))
                wfe_scores.append(wfe)

        if not wfe_scores: return False

        avg_wfe = sum(wfe_scores) / len(wfe_scores)
        quant_logger.info(f"Walk Forward Efficiency (WFE): {avg_wfe*100:.2f}%")

        return avg_wfe > 0.50 # Must be > 50% efficient
