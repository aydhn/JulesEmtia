import numpy as np
import pandas as pd
from core.logger import logger

class MonteCarloSimulator:
    @staticmethod
    def run_simulation(trades_pnl: list, initial_capital=10000.0, num_simulations=10000):
        if not trades_pnl: return None

        results = []
        max_drawdowns = []

        for _ in range(num_simulations):
            simulated_trades = np.random.choice(trades_pnl, size=len(trades_pnl), replace=True)
            cumulative_capital = initial_capital + np.cumsum(simulated_trades)

            peak = np.maximum.accumulate(cumulative_capital)
            drawdown = (cumulative_capital - peak) / peak

            max_dd = abs(np.min(drawdown))
            max_drawdowns.append(max_dd)
            results.append(cumulative_capital[-1])

        risk_of_ruin = sum(1 for cap in results if cap < initial_capital * 0.5) / num_simulations
        expected_md_99 = np.percentile(max_drawdowns, 99)

        logger.info(f"Monte Carlo Stres Testi - İflas Riski: %{risk_of_ruin*100:.2f}, %99 Güven Aralığında Max DD: %{expected_md_99*100:.2f}")

        return {
            'risk_of_ruin': risk_of_ruin,
            'max_dd_99': expected_md_99
        }
