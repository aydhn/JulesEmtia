import pandas as pd
import numpy as np
import sqlite3
import logging

logger = logging.getLogger(__name__)

class MonteCarloSimulator:
    """
    Phase 22: Monte Carlo Simulation and Risk of Ruin
    """
    def __init__(self, db_path: str = "paper_db.sqlite3", simulations: int = 10000):
        self.db_path = db_path
        self.simulations = simulations

    def _get_trade_returns(self) -> np.ndarray:
        try:
            conn = sqlite3.connect(self.db_path)
            # Assuming starting capital is 10000, we calculate % return per trade
            df = pd.read_sql("SELECT pnl FROM trades WHERE status = 'Closed'", conn)
            conn.close()
            if df.empty: return np.array([])
            return (df['pnl'] / 10000.0).values
        except Exception as e:
            logger.error(f"Failed to fetch returns for Monte Carlo: {e}")
            return np.array([])

    def run_simulation(self) -> dict:
        returns = self._get_trade_returns()
        if len(returns) < 10:
            return {"error": "Not enough trades to run Monte Carlo."}

        num_trades = len(returns)

        # Vectorized Monte Carlo using random choices with replacement
        # Shape: (simulations, num_trades)
        sim_indices = np.random.choice(len(returns), size=(self.simulations, num_trades), replace=True)
        sim_returns = returns[sim_indices]

        # Calculate cumulative returns over each simulation
        cum_returns = np.cumprod(1 + sim_returns, axis=1)

        # Calculate Max Drawdown for each simulation
        running_max = np.maximum.accumulate(cum_returns, axis=1)
        drawdowns = (cum_returns - running_max) / running_max
        max_drawdowns = np.min(drawdowns, axis=1) # Note: drawdowns are negative

        # Calculate Risk of Ruin (probability of losing 50% or more)
        ruin_events = np.sum(np.any(cum_returns <= 0.5, axis=1))
        risk_of_ruin = ruin_events / self.simulations

        # Confidence Intervals
        expected_mdd_95 = np.percentile(max_drawdowns, 5) # 5th percentile because they are negative
        expected_mdd_99 = np.percentile(max_drawdowns, 1)

        result = {
            "risk_of_ruin": risk_of_ruin,
            "expected_mdd_95": abs(expected_mdd_95),
            "expected_mdd_99": abs(expected_mdd_99)
        }

        logger.info(f"Monte Carlo complete. Risk of Ruin: {risk_of_ruin:.2%}, 99% CI MDD: {abs(expected_mdd_99):.2%}")
        return result
