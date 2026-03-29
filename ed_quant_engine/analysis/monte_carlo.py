import numpy as np
import pandas as pd

class MonteCarloSimulator:
    def __init__(self, num_simulations=10000):
        self.num_simulations = num_simulations

    def risk_of_ruin(self, trades_df: pd.DataFrame) -> tuple:
        if trades_df.empty or len(trades_df) < 5: return 0.0, 0.0

        pnl_array = trades_df['pnl'].fillna(0).values
        ruin_count = 0
        max_drawdowns = []

        # Vectorized random sampling with replacement
        simulations = np.random.choice(pnl_array, size=(self.num_simulations, len(pnl_array)), replace=True)
        cumulative_paths = np.cumsum(simulations, axis=1)

        for path in cumulative_paths:
            peak = np.maximum.accumulate(path)
            drawdown = (peak - path) / (10000 + peak)  # Assuming base 10k capital
            max_drawdowns.append(np.max(drawdown))

            # Risk of ruin condition (-50% capital lost)
            if np.min(path) < -5000:
                ruin_count += 1

        risk_of_ruin = (ruin_count / self.num_simulations) * 100
        expected_mdd_99 = np.percentile(max_drawdowns, 99) * 100

        return risk_of_ruin, expected_mdd_99
