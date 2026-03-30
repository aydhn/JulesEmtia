import numpy as np
from typing import List, Dict, Any
from src.logger import get_logger

logger = get_logger("monte_carlo")

def run_monte_carlo(pnl_pcts: List[float], initial_balance: float = 10000.0, num_simulations: int = 10000) -> Dict[str, Any]:
    """Runs a Monte Carlo simulation on historical trade returns to assess Risk of Ruin."""
    if not pnl_pcts or len(pnl_pcts) < 20:
        logger.warning("Not enough trade data for a reliable Monte Carlo simulation (Need > 20 trades).")
        return {}

    n_trades = len(pnl_pcts)
    returns_array = np.array(pnl_pcts)

    # 1. Vectorized resampling with replacement
    # Shape: (num_simulations, n_trades)
    simulated_returns = np.random.choice(returns_array, size=(num_simulations, n_trades), replace=True)

    # 2. Convert to equity curves
    # Add 1.0 to returns (e.g., 0.02 -> 1.02) and cumulative product
    equity_curves = np.cumprod(1 + simulated_returns, axis=1) * initial_balance

    # 3. Max Drawdown Calculation for each simulation
    running_max = np.maximum.accumulate(equity_curves, axis=1)
    drawdowns = (equity_curves - running_max) / running_max
    max_drawdowns = np.min(drawdowns, axis=1) # The worst DD for each simulation

    # 4. Final Equity for each simulation
    final_equities = equity_curves[:, -1]

    # 5. Extract Quant Metrics
    expected_dd_95 = np.percentile(max_drawdowns, 5) # 5th percentile worst case
    expected_dd_99 = np.percentile(max_drawdowns, 1) # 1st percentile worst case

    # Risk of Ruin (Losing > 50% of initial balance)
    ruin_threshold = initial_balance * 0.50
    ruined_sims = np.sum(final_equities < ruin_threshold)
    risk_of_ruin_pct = (ruined_sims / num_simulations) * 100

    logger.info(f"Monte Carlo ({num_simulations} sims) -> RoR: {risk_of_ruin_pct:.2f}%, 99% MaxDD: {expected_dd_99:.2%}")

    return {
        "Num_Simulations": num_simulations,
        "Risk_Of_Ruin_Pct": risk_of_ruin_pct,
        "Expected_MaxDD_95": expected_dd_95,
        "Expected_MaxDD_99": expected_dd_99,
        "Median_Final_Equity": np.median(final_equities)
    }
