import pandas as pd
import numpy as np
from src.logger import get_logger
from src.backtester import vectorized_backtest

logger = get_logger("walk_forward")

def walk_forward_optimization(df: pd.DataFrame, train_size: int = 500, test_size: int = 100) -> pd.DataFrame:
    """Performs an out-of-sample Walk-Forward Optimization to detect curve-fitting."""
    results = []

    if len(df) < (train_size + test_size):
        logger.warning("Dataset too small for walk-forward optimization.")
        return pd.DataFrame()

    for start in range(0, len(df) - train_size - test_size, test_size):
        train_end = start + train_size
        test_end = train_end + test_size

        df_train = df.iloc[start:train_end]
        df_test = df.iloc[train_end:test_end]

        # Here we would normally optimize parameters on df_train.
        # Since our parameters are mostly static by design, we just run the backtest
        # on IS (In-Sample) and OOS (Out-Of-Sample) to calculate Efficiency.

        res_is = vectorized_backtest(df_train)
        res_oos = vectorized_backtest(df_test)

        is_ret = res_is.get("Total_Return", 0.0)
        oos_ret = res_oos.get("Total_Return", 0.0)

        # Walk Forward Efficiency (WFE)
        # Annualized OOS / Annualized IS
        # For simplicity, we just use raw returns over the period
        wfe = (oos_ret / is_ret) if is_ret > 0 else 0.0

        results.append({
            "Start_Idx": start,
            "IS_Return": is_ret,
            "OOS_Return": oos_ret,
            "WFE": wfe,
            "Robust": wfe > 0.50 # WFE > 50% means the model is somewhat robust
        })

    df_results = pd.DataFrame(results)
    avg_wfe = df_results['WFE'].mean()

    logger.info(f"Walk-Forward Analysis complete. Average WFE: {avg_wfe:.2f}")
    if avg_wfe < 0.50:
        logger.critical(f"STRATEGY OVERFITTED! Walk-Forward Efficiency ({avg_wfe:.2f}) < 0.50")

    return df_results
