import pandas as pd
import numpy as np
from logger import get_logger

log = get_logger()

def backtest_strategy(df: pd.DataFrame, params: dict):
    """
    Vectorized historical backtest. (Phase 7).
    """
    pass

def walk_forward_optimization(df: pd.DataFrame, n_windows: int = 4):
    """
    Walk-Forward Optimization (Phase 14).
    Calculates Walk-Forward Efficiency (WFE) to prevent curve-fitting.
    If WFE < 50%, the parameters are rejected as overfitted.
    """
    pass

def run_monte_carlo(pnl_pcts: list, n_simulations=10000, initial_capital=10000.0) -> dict:
    """
    Monte Carlo Risk of Ruin & Drawdown Simulation (Phase 22).
    Vectorised operations to prevent CPU hogging.
    Returns the expected maximum drawdown at 95% and 99% Confidence Intervals,
    along with Risk of Ruin (probability of losing 50% capital).
    """
    if not pnl_pcts or len(pnl_pcts) < 10:
        return {"max_dd_95": 0, "max_dd_99": 0, "risk_of_ruin": 0}

    pnl_array = np.array(pnl_pcts)
    n_trades = len(pnl_array)

    # Random choice with replacement (10,000 paths of n_trades length)
    sim_paths = np.random.choice(pnl_array, size=(n_simulations, n_trades), replace=True)

    # Calculate cumulative returns
    cum_returns = np.cumprod(1 + sim_paths, axis=1) * initial_capital

    # Calculate Drawdowns
    running_max = np.maximum.accumulate(cum_returns, axis=1)
    drawdowns = (cum_returns - running_max) / running_max
    max_drawdowns = np.min(drawdowns, axis=1) # Min because drawdowns are negative

    max_dd_95 = np.percentile(max_drawdowns, 5) # 5th percentile of negative numbers
    max_dd_99 = np.percentile(max_drawdowns, 1) # 1st percentile

    # Risk of Ruin: paths that drop below 50% of initial
    ruined_paths = np.sum(np.min(cum_returns, axis=1) < (initial_capital * 0.5))
    risk_of_ruin = ruined_paths / n_simulations

    log.info(f"Monte Carlo Results: 99% DD={max_dd_99:.2%}, Ruin={risk_of_ruin:.2%}")
    return {"max_dd_95": abs(max_dd_95), "max_dd_99": abs(max_dd_99), "risk_of_ruin": risk_of_ruin}
