import numpy as np
import pandas as pd
from logger import logger

class MonteCarloSimulator:
    def __init__(self, num_simulations=10000):
        self.num_simulations = num_simulations

    def run_simulation(self, trade_pnls: list) -> dict:
        '''
        Phase 22: Monte Carlo Risk Validation
        Resamples trade returns to calculate Expected Drawdown & Risk of Ruin
        '''
        if not trade_pnls or len(trade_pnls) < 10:
             return {"Error": "Not enough trades for simulation."}

        pnls = np.array(trade_pnls)
        sim_results = []
        max_drawdowns = []
        ruin_count = 0
        ruin_threshold = 0.50 # 50% loss = Ruin

        for _ in range(self.num_simulations):
             # Resample with replacement
             sim_trades = np.random.choice(pnls, size=len(pnls), replace=True)

             # Calculate equity curve
             equity = 1.0 + sim_trades.cumsum()

             # Check for ruin
             if np.any(equity <= (1.0 - ruin_threshold)):
                  ruin_count += 1

             # Calculate Drawdown
             peak = np.maximum.accumulate(equity)
             drawdown = (equity - peak) / peak
             max_drawdowns.append(drawdown.min())

        risk_of_ruin = ruin_count / self.num_simulations
        expected_dd_95 = np.percentile(max_drawdowns, 5) # 5th percentile because DDs are negative
        expected_dd_99 = np.percentile(max_drawdowns, 1)

        logger.info(f"Monte Carlo: Risk of Ruin = {risk_of_ruin:.2%}, 99% Max DD = {expected_dd_99:.2%}")

        return {
             "Risk_of_Ruin": risk_of_ruin,
             "Max_DD_95": expected_dd_95,
             "Max_DD_99": expected_dd_99
        }