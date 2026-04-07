import numpy as np
import pandas as pd
from typing import Dict
from .logger import quant_logger

class MonteCarloSimulator:
    @staticmethod
    def run_simulation(closed_trades: pd.DataFrame, n_sims: int = 10000) -> Dict:
        """Phase 22: Fast Vectorized Monte Carlo & Risk of Ruin"""
        if closed_trades.empty or len(closed_trades) < 10:
            return {"max_dd_99": 0.0, "risk_of_ruin": 0.0}

        returns = closed_trades['net_pnl'].values / 10000.0 # Assuming 10k start logic for pct
        n_trades = len(returns)

        # Vectorized simulation with replacement
        sims = np.random.choice(returns, size=(n_sims, n_trades), replace=True)

        # Cumulative returns
        cum_returns = np.cumsum(sims, axis=1)

        # Drawdowns
        running_max = np.maximum.accumulate(cum_returns, axis=1)
        drawdowns = cum_returns - running_max
        max_drawdowns = np.min(drawdowns, axis=1)

        # Metrics
        max_dd_99 = np.percentile(max_drawdowns, 1) # 1st percentile (worst 1%)

        # Risk of Ruin (Losing > 50%)
        ruin_count = np.sum(np.any(cum_returns <= -0.50, axis=1))
        risk_of_ruin = ruin_count / n_sims

        if risk_of_ruin > 0.01:
            quant_logger.warning(f"HIGH RISK OF RUIN DETECTED: {risk_of_ruin*100:.2f}%")

        return {
            "max_dd_99": max_dd_99 * 100, # as percentage
            "risk_of_ruin": risk_of_ruin * 100
        }
