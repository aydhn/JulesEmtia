from __future__ import annotations

import numpy as np

import src.paper_db as db
from src.config import INITIAL_BALANCE
from src.logger import get_logger

logger = get_logger()

# Ruin is defined as losing more than 50% of starting capital.
_RUIN_THRESHOLD = INITIAL_BALANCE * 0.5


def run_monte_carlo(simulations: int = 10_000) -> dict:
    """Bootstrap Monte Carlo simulation over closed trade returns.

    Returns a dict with ``expected_max_drawdown_99`` (% at 99th percentile)
    and ``risk_of_ruin_pct``. Returns an empty dict when fewer than 20
    closed trades are available.
    """
    df = db.get_closed_trades()
    if len(df) < 20:
        logger.warning("Not enough trades for Monte Carlo simulation (%s < 20).", len(df))
        return {}

    pnl_pcts = df["pnl_pct"].values
    max_drawdowns: list[float] = []
    final_balances: list[float] = []
    ruin_count = 0

    rng = np.random.default_rng()
    for _ in range(simulations):
        sim_returns = rng.choice(pnl_pcts, size=len(pnl_pcts), replace=True)

        balance = float(INITIAL_BALANCE)
        peak = balance
        max_dd = 0.0
        ruined = False

        for ret in sim_returns:
            balance *= 1.0 + float(ret)
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            if balance <= _RUIN_THRESHOLD:
                ruin_count += 1
                ruined = True
                break

        max_drawdowns.append(max_dd)
        if not ruined:
            final_balances.append(balance)

    expected_md_99 = float(np.percentile(max_drawdowns, 99)) * 100.0
    risk_of_ruin = (ruin_count / simulations) * 100.0

    result = {
        "expected_max_drawdown_99": expected_md_99,
        "risk_of_ruin_pct": risk_of_ruin,
    }
    logger.info(
        "Monte Carlo: 99%% CI Max DD=%.2f%% Risk of Ruin=%.2f%%",
        expected_md_99,
        risk_of_ruin,
    )
    return result
