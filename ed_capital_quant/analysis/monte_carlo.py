import pandas as pd
import numpy as np
from core.logger import setup_logger
from typing import Dict

logger = setup_logger("monte_carlo")

class MonteCarloEngine:
    """
    Phase 22: Fast vectorized Monte Carlo Risk Validation & Risk of Ruin calculation.
    """
    def __init__(self, broker, simulations: int = 10000):
        self.broker = broker
        self.simulations = simulations

    def run_simulation(self) -> Dict:
        """
        Samples historical trades with replacement to simulate alternate universes.
        """
        logger.info(f"Running Monte Carlo Stress Test ({self.simulations} simulations)...")
        closed_trades = self.broker.get_closed_positions()

        if len(closed_trades) < 20:
            logger.warning("Not enough closed trades for statistically significant Monte Carlo simulation.")
            return {"var_99": 0.0, "risk_of_ruin": 0.0}

        df = pd.DataFrame(closed_trades)
        pnl_pcts = df['pnl'] / self.broker.initial_balance # Approximate percentage return per trade

        trade_count = len(pnl_pcts)

        # Create a matrix of shape (simulations, trade_count) with random samples
        # Vectorized for extreme speed
        samples = np.random.choice(pnl_pcts.values, size=(self.simulations, trade_count), replace=True)

        # Cumulative returns for each simulation path
        # Assuming starting capital is 1.0 (100%)
        cumulative_paths = np.cumprod(1 + samples, axis=1)

        # Calculate Drawdowns for each path
        running_max = np.maximum.accumulate(cumulative_paths, axis=1)
        drawdowns = (cumulative_paths - running_max) / running_max
        max_drawdowns = np.min(drawdowns, axis=1) # The worst drop in each simulation

        # Risk Metrics
        var_99 = np.percentile(max_drawdowns, 1) * 100 # 1st percentile (worst 1%)

        # Risk of Ruin: Probability of dropping below 50% of starting capital at any point
        ruined_simulations = np.sum(np.min(cumulative_paths, axis=1) < 0.50)
        risk_of_ruin = ruined_simulations / self.simulations

        logger.info(f"Monte Carlo Results | 99% CI MaxDD: {var_99:.2f}% | Risk of Ruin: {risk_of_ruin:.2%}")

        if risk_of_ruin > 0.01:
            logger.critical(f"Kelly Fraction is too aggressive! Risk of Ruin is {risk_of_ruin:.2%}")

        return {
            "var_99": var_99,
            "risk_of_ruin": risk_of_ruin
        }
