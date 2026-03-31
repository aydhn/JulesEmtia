import pandas as pd
import numpy as np
from paper_db import PaperDB
from logger import logger

class MonteCarloRisk:
    """
    Phase 22: Monte Carlo Risk Validation & Risk of Ruin.
    Stress-tests the strategy using historical trades to simulate future worst-case scenarios.
    Vectorized NumPy operations for ultra-fast performance.
    """

    @classmethod
    def run_simulation(cls, n_simulations: int = 10000, max_drawdown_limit: float = 0.50) -> dict:
        """
        Runs Monte Carlo simulations on historical trade PnLs.
        Returns critical risk metrics: Expected Max Drawdown (99% CI) and Risk of Ruin.
        """
        rows = PaperDB.fetch_all("SELECT net_pnl FROM trades WHERE status = 'Closed' ORDER BY exit_time ASC")

        if len(rows) < 30:
            logger.warning("Not enough closed trades (min 30) for reliable Monte Carlo simulation.")
            return {"99% CI Expected Max Drawdown": "N/A", "Risk of Ruin": "N/A"}

        pnls = np.array([row['net_pnl'] for row in rows])
        n_trades = len(pnls)

        logger.info(f"Running {n_simulations} Monte Carlo simulations on {n_trades} trades...")

        # 1. Vectorized Monte Carlo Simulation (Bootstrap sampling with replacement)
        # Create a matrix of shape (n_simulations, n_trades)
        simulated_returns_matrix = np.random.choice(pnls, size=(n_simulations, n_trades), replace=True)

        # 2. Calculate Equity Curves
        start_bal = 10000.0 # Default assumption
        cumulative_pnl = np.cumsum(simulated_returns_matrix, axis=1)
        equity_curves = start_bal + cumulative_pnl

        # 3. Calculate Drawdowns for each simulation
        peak_equity = np.maximum.accumulate(equity_curves, axis=1)
        drawdowns = (equity_curves - peak_equity) / peak_equity
        max_drawdowns_per_sim = np.min(drawdowns, axis=1) * 100 # Convert to percentage

        # 4. Critical Risk Metrics
        expected_mdd_95 = np.percentile(max_drawdowns_per_sim, 5) # 5th percentile (most negative)
        expected_mdd_99 = np.percentile(max_drawdowns_per_sim, 1) # 1st percentile

        # Risk of Ruin: Percentage of simulations where Max Drawdown exceeded the limit (e.g. 50%)
        ruin_limit_pct = -abs(max_drawdown_limit) * 100
        ruined_sims = np.sum(max_drawdowns_per_sim <= ruin_limit_pct)
        risk_of_ruin = (ruined_sims / n_simulations) * 100

        logger.info(f"Monte Carlo Risk Analysis Complete. Risk of Ruin: {risk_of_ruin:.2f}%, 99% Expected Max DD: {expected_mdd_99:.2f}%")

        if risk_of_ruin > 1.0:
            logger.critical(f"WARNING: Risk of Ruin is {risk_of_ruin:.2f}% (> 1.0%). Strategy sizing is too aggressive! Reduce Kelly Fraction.")

        return {
            "95% CI Expected Max Drawdown": f"{expected_mdd_95:.2f}%",
            "99% CI Expected Max Drawdown": f"{expected_mdd_99:.2f}%",
            "Risk of Ruin": f"{risk_of_ruin:.2f}%"
        }

