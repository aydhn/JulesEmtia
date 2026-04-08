import numpy as np
import pandas as pd
import src.paper_db as db
from src.logger import get_logger

logger = get_logger()

def run_monte_carlo(simulations=10000) -> dict:
    df = db.get_closed_trades()
    if len(df) < 20:
        logger.warning("Not enough trades for Monte Carlo simulation.")
        return {}

    pnl_pcts = df['pnl_pct'].values

    max_drawdowns = []
    final_balances = []
    ruin_count = 0

    for _ in range(simulations):
        # Sample with replacement
        sim_trades = np.random.choice(pnl_pcts, size=len(pnl_pcts), replace=True)

        balance = 10000.0
        peak = balance
        max_dd = 0.0

        for pct in sim_trades:
            balance *= (1 + pct)
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak
            if dd > max_dd:
                max_dd = dd
            if balance <= 5000.0: # Ruin threshold 50%
                ruin_count += 1
                break

        max_drawdowns.append(max_dd)
        final_balances.append(balance)

    expected_md_99 = np.percentile(max_drawdowns, 99)
    risk_of_ruin = (ruin_count / simulations) * 100

    res = {
        "expected_max_drawdown_99": expected_md_99 * 100,
        "risk_of_ruin_pct": risk_of_ruin
    }
    logger.info(f"Monte Carlo Results: 99% CI Max DD: {res['expected_max_drawdown_99']:.2f}%, Risk of Ruin: {res['risk_of_ruin_pct']:.2f}%")
    return res
