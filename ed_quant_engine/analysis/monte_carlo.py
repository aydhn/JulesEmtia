import numpy as np
import pandas as pd
import sqlite3
from ed_quant_engine.core.logger import logger
import ed_quant_engine.config as config

def run_monte_carlo_simulation(num_simulations: int = 10000) -> dict:
    """
    Monte Carlo Risk Validation & Risk of Ruin Engine (Phase 22).
    Vectorized NumPy implementation for speed.
    """
    try:
        with sqlite3.connect(config.DB_PATH) as conn:
            df = pd.read_sql_query("SELECT pnl FROM trades WHERE status = 'Closed'", conn)

        if df.empty or len(df) < 10:
            logger.warning("Not enough closed trades for Monte Carlo Simulation (Need > 10)")
            return {}

        # Convert PnL to percentage of initial capital (simplified)
        # In a real environment, you'd track compounding capital. Here we approximate returns.
        returns = df['pnl'].values / config.INITIAL_CAPITAL

        n_trades = len(returns)

        # Create (num_simulations, n_trades) array of random choices from historical returns
        simulations = np.random.choice(returns, size=(num_simulations, n_trades), replace=True)

        # Add 1 to returns and calculate cumulative product along the trades axis
        cumulative_returns = np.cumprod(1 + simulations, axis=1)

        # Calculate Drawdowns
        running_max = np.maximum.accumulate(cumulative_returns, axis=1)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdowns = np.min(drawdowns, axis=1) # Min because DD is negative

        # Risk of Ruin (Ruin defined as > 50% drawdown)
        ruin_events = np.sum(max_drawdowns <= -0.50)
        risk_of_ruin = (ruin_events / num_simulations) * 100

        # Expected Max Drawdown at 95% and 99% CI
        expected_dd_95 = np.percentile(max_drawdowns, 5) * 100 # 5th percentile is worst 5%
        expected_dd_99 = np.percentile(max_drawdowns, 1) * 100 # 1st percentile is worst 1%

        results = {
            "Simulations": num_simulations,
            "Risk of Ruin (>50% Loss)": f"{risk_of_ruin:.2f}%",
            "95% CI Max Drawdown": f"{expected_dd_95:.2f}%",
            "99% CI Max Drawdown": f"{expected_dd_99:.2f}%",
            "Median End Capital": f"${config.INITIAL_CAPITAL * np.median(cumulative_returns[:, -1]):.2f}"
        }

        logger.info(f"Monte Carlo Risk Analysis Complete: {results}")

        if risk_of_ruin > 1.0:
            logger.critical(f"HIGH RISK OF RUIN DETECTED: {risk_of_ruin:.2f}% > 1.0%. Adjust Kelly Multiplier!")

        return results

    except Exception as e:
        logger.error(f"Monte Carlo Simulation Error: {e}")
        return {}
