import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config

logger = setup_logger("MonteCarlo")

class MonteCarloSimulator:
    def __init__(self, n_simulations=10000):
        self.n_simulations = n_simulations

    def run_simulation(self, closed_trades_df: pd.DataFrame, initial_capital=Config.BASE_CAPITAL) -> dict:
        """Runs fast vectorized Monte Carlo on historical PnL percentages."""
        if closed_trades_df.empty or len(closed_trades_df) < 10:
             logger.warning("Not enough closed trades for Monte Carlo simulation.")
             return {}

        # Calculate PnL as percentage of capital at that time (Simplified approximation)
        pnl_pcts = (closed_trades_df['pnl'] / initial_capital).values
        n_trades = len(pnl_pcts)

        # Vectorized random sampling with replacement
        simulated_paths = np.random.choice(pnl_pcts, size=(self.n_simulations, n_trades), replace=True)

        # Cumulative product of (1 + return) to get equity curves
        equity_curves = initial_capital * np.cumprod(1 + simulated_paths, axis=1)

        # Calculate Max Drawdowns for each path
        running_max = np.maximum.accumulate(equity_curves, axis=1)
        drawdowns = (running_max - equity_curves) / running_max
        max_drawdowns = np.max(drawdowns, axis=1)

        # Risk of Ruin (Ruin Threshold: 50% loss)
        ruin_threshold = initial_capital * 0.5
        ruined_sims = np.any(equity_curves < ruin_threshold, axis=1)
        risk_of_ruin_pct = np.mean(ruined_sims) * 100

        # Confidence Intervals
        expected_mdd_95 = np.percentile(max_drawdowns, 95) * 100
        expected_mdd_99 = np.percentile(max_drawdowns, 99) * 100

        logger.info(f"Monte Carlo ({self.n_simulations} sims) -> RoR: {risk_of_ruin_pct:.2f}%, 99% MDD: {expected_mdd_99:.2f}%")

        # Plot Spaghetti Curve
        self._plot_spaghetti(equity_curves, n_trades)

        return {
            "risk_of_ruin": risk_of_ruin_pct,
            "mdd_95": expected_mdd_95,
            "mdd_99": expected_mdd_99
        }

    def _plot_spaghetti(self, equity_curves: np.ndarray, n_trades: int):
        plt.figure(figsize=(10, 6))

        # Plot a subset of curves for visibility (alpha blending)
        n_plot = min(100, self.n_simulations)
        plt.plot(np.arange(n_trades), equity_curves[:n_plot].T, alpha=0.1, color='blue')

        # Plot mean curve
        mean_curve = np.mean(equity_curves, axis=0)
        plt.plot(np.arange(n_trades), mean_curve, color='red', linewidth=2, label="Mean Expectancy")

        plt.title('Monte Carlo Risk of Ruin Simulation (10,000 Paths)')
        plt.xlabel('Trades')
        plt.ylabel('Portfolio Equity')
        plt.axhline(y=Config.BASE_CAPITAL * 0.5, color='black', linestyle='--', label='Ruin Threshold (50%)')
        plt.legend()

        os.makedirs(Config.REPORT_DIR, exist_ok=True)
        plt.savefig(os.path.join(Config.REPORT_DIR, "monte_carlo.png"))
        plt.close()
