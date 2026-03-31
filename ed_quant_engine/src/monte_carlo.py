import numpy as np
import pandas as pd
from typing import List, Dict
from src.paper_db import db
from src.logger import logger

class MonteCarloSimulator:
    def __init__(self, simulations: int = 10000, start_capital: float = 10000.0):
        self.simulations = simulations
        self.start_capital = start_capital

    def _get_historical_pnls(self) -> List[float]:
        """
        Fetches PnL percentages from closed trades in paper_db.
        """
        try:
            db.cursor.execute("SELECT pnl FROM trades WHERE status = 'Closed' AND pnl IS NOT NULL")
            results = db.cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Error fetching historical PnLs for Monte Carlo: {e}")
            return []

    def run_simulation(self) -> Dict:
        """
        Runs Monte Carlo simulation by randomly resampling historical PnL sequences.
        """
        historical_pnls = self._get_historical_pnls()
        if not historical_pnls or len(historical_pnls) < 10:
             logger.warning("Not enough historical trades for Monte Carlo simulation.")
             return {}

        logger.info(f"Starting Monte Carlo with {self.simulations} simulations using {len(historical_pnls)} trades.")

        # Convert to numpy array for speed
        pnls = np.array(historical_pnls)

        # Preallocate memory for results
        final_returns = np.zeros(self.simulations)
        max_drawdowns = np.zeros(self.simulations)

        # Vectorized resampling
        # Matrix shape: (num_simulations, num_trades_to_simulate)
        # We simulate the same number of trades as we have history for.
        num_trades = len(pnls)

        for i in range(self.simulations):
            # Sample with replacement
            simulated_pnls = np.random.choice(pnls, size=num_trades, replace=True)

            # Cumulative return (Compounding)
            # Assuming Kelly-sized returns are percentage of capital
            cumulative_returns = np.cumprod(1 + simulated_pnls)

            final_returns[i] = cumulative_returns[-1]

            # Drawdown Calculation
            rolling_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = (cumulative_returns - rolling_max) / rolling_max
            max_drawdowns[i] = np.min(drawdowns)

        # Calculate Risk Metrics
        expected_mdd_95 = np.percentile(max_drawdowns, 5)  # 5th percentile is worst 5% case
        expected_mdd_99 = np.percentile(max_drawdowns, 1)  # 1st percentile is worst 1% case

        # Risk of Ruin: Probability of losing 50% or more (i.e. return < 0.5)
        # If any path's lowest point drops below 0.5 of initial, we consider it ruin.
        # But for simplicity, we just look at the final return distribution or the MDD distribution.
        # Let's say Ruin = MDD > 50%
        ruin_events = np.sum(max_drawdowns <= -0.50)
        risk_of_ruin = ruin_events / self.simulations

        results = {
            "Simulations": self.simulations,
            "Trades Simulated per Run": num_trades,
            "Median Return": np.median(final_returns),
            "Expected Max Drawdown (95% CI)": expected_mdd_95,
            "Expected Max Drawdown (99% CI)": expected_mdd_99,
            "Risk of Ruin (MDD > 50%)": risk_of_ruin
        }

        logger.info(f"Monte Carlo Results: MDD 99%: {expected_mdd_99:.2f}, Ruin Risk: {risk_of_ruin:.4f}")
        return results

