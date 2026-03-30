import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from logger import log
import paper_db

def run_monte_carlo(simulations: int = 10000, max_trades: int = 500) -> Dict:
    """
    Monte Carlo Risk Validation Engine (Phase 22).
    Simulates thousands of alternative trade sequences by sampling historical PnLs with replacement.
    Calculates expected Max Drawdown and Risk of Ruin at 95% and 99% Confidence Intervals.
    """
    try:
        query = "SELECT pnl FROM trades WHERE status = 'Closed'"
        trades_pnl = paper_db.fetch_dataframe(query)

        if trades_pnl.empty or len(trades_pnl) < 10:
            log.warning("Not enough closed trades for Monte Carlo Simulation.")
            return {
                "max_dd_95": 0.0,
                "max_dd_99": 0.0,
                "risk_of_ruin": 0.0,
                "median_profit": 0.0
            }

        pnls = trades_pnl['pnl'].values
        initial_capital = 10000.0 # From .env conceptually, but we simulate % growth

        # Convert PnLs to % returns for realistic simulation scaling
        returns = pnls / initial_capital

        simulated_equity_curves = np.zeros((simulations, max_trades))
        max_drawdowns = np.zeros(simulations)
        ruin_count = 0
        ruin_threshold = 0.5 # 50% loss = Ruin

        for i in range(simulations):
            # Sample with replacement
            simulated_returns = np.random.choice(returns, size=max_trades, replace=True)

            # Calculate cumulative equity curve (Starting at 1.0)
            equity_curve = np.cumprod(1 + simulated_returns)
            simulated_equity_curves[i] = equity_curve

            # Calculate Max Drawdown for this path
            peak = np.maximum.accumulate(equity_curve)
            drawdown = (peak - equity_curve) / peak
            max_dd = np.max(drawdown)
            max_drawdowns[i] = max_dd

            # Check Risk of Ruin
            if np.min(equity_curve) <= (1.0 - ruin_threshold):
                ruin_count += 1

        # Aggregate Metrics
        max_dd_95 = np.percentile(max_drawdowns, 95) # Expected Max DD in worst 5% of cases
        max_dd_99 = np.percentile(max_drawdowns, 99) # Expected Max DD in worst 1% of cases
        risk_of_ruin = (ruin_count / simulations) * 100.0
        median_profit = (np.median(simulated_equity_curves[:, -1]) - 1.0) * 100.0

        if risk_of_ruin > 1.0:
            log.warning(f"🚨 MONTE CARLO ALERT: Risk of Ruin is dangerously high ({risk_of_ruin:.2f}%). Fractional Kelly too aggressive.")

        log.info(f"Monte Carlo Completed: 99% Max DD = {max_dd_99*100:.2f}%, Risk of Ruin = {risk_of_ruin:.2f}%")

        return {
            "max_dd_95": max_dd_95 * 100,
            "max_dd_99": max_dd_99 * 100,
            "risk_of_ruin": risk_of_ruin,
            "median_profit": median_profit
        }

    except Exception as e:
        log.error(f"Monte Carlo simulation failed: {e}")
        return {
            "max_dd_95": 0.0,
            "max_dd_99": 0.0,
            "risk_of_ruin": 0.0,
            "median_profit": 0.0
        }
