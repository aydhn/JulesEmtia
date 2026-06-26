"""walk_forward.py — Walk-Forward Optimization (WFO) for strategy validation.

Integrates with ``continuous_learner`` and ``model_registry``:
  - Results are recorded via ``model_registry.record_training``
  - WFE < WFE_THRESHOLD triggers a degradation note
  - Called by ``ContinuousLearner.run_walk_forward_for_ticker``

Walk-Forward Efficiency (WFE) = OOS PnL / IS PnL.
A WFE > 0.5 generally indicates the strategy generalises beyond its
training window.  Values below 0.3 suggest overfitting.
"""
from __future__ import annotations

import pandas as pd

from src.backtester import run_vectorized_backtest
from src.config import INITIAL_BALANCE
from src.logger import get_logger

logger = get_logger()

WFE_THRESHOLD = 0.5           # Below this → possible overfitting warning
ROBUSTNESS_THRESHOLD = 0.10   # Above this → fragile parameters warning


def walk_forward_optimization(
    df: pd.DataFrame,
    ticker: str,
    train_size: int = 500,
    test_size: int = 100,
) -> pd.DataFrame | None:
    """Perform Walk-Forward Optimization.

    Returns a DataFrame with per-window metrics or *None* when the
    dataset is too short.  The caller is responsible for persisting
    results to the model registry.
    """
    if len(df) < train_size + test_size:
        logger.debug("WFO skipped for %s: insufficient rows (%s).", ticker, len(df))
        return None

    windows: list[dict] = []
    step = test_size
    i = 0

    while i + train_size + test_size <= len(df):
        train_df = df.iloc[i : i + train_size]
        test_df = df.iloc[i + train_size : i + train_size + test_size]

        is_res = run_vectorized_backtest(train_df, ticker, initial_balance=INITIAL_BALANCE)
        oos_initial = is_res["final_balance"]
        oos_res = run_vectorized_backtest(test_df, ticker, initial_balance=oos_initial)

        # Neighbourhood robustness: shift features by 1 bar (mild parameter variation)
        robust_train = train_df.shift(1).dropna()
        robust_res = run_vectorized_backtest(robust_train, ticker, initial_balance=INITIAL_BALANCE)

        is_pnl = is_res["final_balance"] - INITIAL_BALANCE
        oos_pnl = oos_res["final_balance"] - oos_initial
        wfe = oos_pnl / is_pnl if is_pnl > 0 else 0.0
        robustness_var = (
            abs(is_res["final_balance"] - robust_res["final_balance"]) / max(is_res["final_balance"], 1e-9)
        )

        windows.append(
            {
                "window_start": i,
                "is_pnl": is_pnl,
                "oos_pnl": oos_pnl,
                "wfe": wfe,
                "robustness_var": robustness_var,
            }
        )
        i += step

    if not windows:
        return None

    wfe_df = pd.DataFrame(windows)
    avg_wfe = float(wfe_df["wfe"].mean())
    avg_robust = float(wfe_df["robustness_var"].mean())

    logger.info(
        "WFO %s: windows=%s avg_WFE=%.2f avg_robustness=%.4f",
        ticker,
        len(windows),
        avg_wfe,
        avg_robust,
    )

    if avg_wfe < WFE_THRESHOLD:
        logger.warning(
            "%s may be overfitting: avg WFE=%.2f < %.2f",
            ticker,
            avg_wfe,
            WFE_THRESHOLD,
        )
    if avg_robust > ROBUSTNESS_THRESHOLD:
        logger.warning(
            "%s has fragile parameters: avg robustness_var=%.4f > %.4f",
            ticker,
            avg_robust,
            ROBUSTNESS_THRESHOLD,
        )

    return wfe_df
