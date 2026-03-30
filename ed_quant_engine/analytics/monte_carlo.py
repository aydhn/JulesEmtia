import numpy as np
import pandas as pd
from core.logger import get_logger

log = get_logger()

def monte_carlo_simulation(trades_pnl: list, initial_balance=10000.0, simulations=10000):
    if not trades_pnl:
        return None

    trades = np.array(trades_pnl)
    n_trades = len(trades)

    # Generate random paths
    simulated_paths = np.random.choice(trades, size=(simulations, n_trades), replace=True)

    # Calculate cumulative returns
    cum_returns = np.cumprod(1 + simulated_paths, axis=1) * initial_balance

    # Calculate Max Drawdown for each path
    peak = np.maximum.accumulate(cum_returns, axis=1)
    drawdowns = (peak - cum_returns) / peak
    max_drawdowns = np.max(drawdowns, axis=1)

    # Calculate Ruin Probability (balance drops below 50%)
    ruin_count = np.sum(np.min(cum_returns, axis=1) < initial_balance * 0.5)
    risk_of_ruin = ruin_count / simulations

    # 95% and 99% CI Expected Max Drawdown
    var_95 = np.percentile(max_drawdowns, 95)
    var_99 = np.percentile(max_drawdowns, 99)

    log.info(f"Monte Carlo: Risk of Ruin {risk_of_ruin*100:.2f}% | 99% CI Max DD: {var_99*100:.2f}%")

    return {
        'Risk_of_Ruin': risk_of_ruin,
        'Max_DD_95': var_95,
        'Max_DD_99': var_99
    }
