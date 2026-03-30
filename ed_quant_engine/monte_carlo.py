import numpy as np
import pandas as pd
from logger import log

def run_monte_carlo(trades_df: pd.DataFrame, num_simulations: int = 10000, initial_capital: float = 10000.0) -> dict:
    """
    Runs Monte Carlo simulation by shuffling historical PnL % returns with replacement.
    """
    if trades_df.empty or 'pnl' not in trades_df.columns:
        return {}

    log.info(f"Running {num_simulations} Monte Carlo simulations...")

    # Extract trade return % (PnL / Capital before trade)
    # Approximation: using initial capital for all returns for simplicity
    returns_pct = (trades_df['pnl'] / initial_capital).values
    num_trades = len(returns_pct)

    if num_trades < 50:
        log.warning("Need at least 50 trades for reliable Monte Carlo.")
        return {}

    # Vectorized Simulation: shape = (num_simulations, num_trades)
    simulated_returns = np.random.choice(returns_pct, size=(num_simulations, num_trades), replace=True)

    # Calculate equity curves
    # Add 1 to returns to calculate cumulative product
    growth_factors = 1 + simulated_returns
    equity_curves = initial_capital * np.cumprod(growth_factors, axis=1)

    # Calculate Max Drawdowns for each simulation
    peaks = np.maximum.accumulate(equity_curves, axis=1)
    drawdowns = (equity_curves - peaks) / peaks
    max_drawdowns = np.min(drawdowns, axis=1) # Min because drawdowns are negative

    # Calculate Risk of Ruin (probability of hitting -50% DD)
    ruin_threshold = -0.50
    ruined_sims = np.sum(max_drawdowns <= ruin_threshold)
    risk_of_ruin = ruined_sims / num_simulations

    # 95% and 99% CI Expected Max Drawdown
    expected_mdd_95 = np.percentile(max_drawdowns, 5) # 5th percentile (worst 5%)
    expected_mdd_99 = np.percentile(max_drawdowns, 1) # 1st percentile

    return {
        "Risk of Ruin": risk_of_ruin,
        "Expected Max DD (95% CI)": expected_mdd_95,
        "Expected Max DD (99% CI)": expected_mdd_99,
        "Simulations": num_simulations
    }
