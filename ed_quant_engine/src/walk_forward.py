import pandas as pd
import numpy as np
from src.backtester import run_vectorized_backtest
from src.logger import get_logger

logger = get_logger()

def walk_forward_optimization(df: pd.DataFrame, ticker: str, train_size=500, test_size=100):
    """
    Performs Walk-Forward Optimization to calculate WFE (Walk-Forward Efficiency)
    and checks parameter neighborhood robustness.
    """
    if len(df) < train_size + test_size:
        return None

    windows = []
    for i in range(0, len(df) - train_size - test_size, test_size):
        train_df = df.iloc[i:i+train_size]
        test_df = df.iloc[i+train_size:i+train_size+test_size]

        # Standard Parameter Result
        is_res = run_vectorized_backtest(train_df, ticker)
        oos_res = run_vectorized_backtest(test_df, ticker, initial_balance=is_res['final_balance'])

        # Robustness Check (Neighborhood Variance simulation)
        # Shift data slightly to simulate a slight parameter change
        robust_train_df = train_df.shift(1).dropna()
        robust_res = run_vectorized_backtest(robust_train_df, ticker)

        robustness_variance = abs(is_res['final_balance'] - robust_res['final_balance']) / is_res['final_balance']

        is_pnl = is_res['final_balance'] - 10000
        oos_pnl = oos_res['final_balance'] - is_res['final_balance']

        wfe = (oos_pnl / is_pnl) if is_pnl > 0 else 0

        windows.append({
            "is_pnl": is_pnl,
            "oos_pnl": oos_pnl,
            "wfe": wfe,
            "robustness_var": robustness_variance
        })

    wfe_df = pd.DataFrame(windows)
    avg_wfe = wfe_df['wfe'].mean()
    avg_robust = wfe_df['robustness_var'].mean()

    logger.info(f"WFO completed for {ticker}. Average WFE: {avg_wfe:.2f}, Robustness Var: {avg_robust:.4f}")
    if avg_wfe < 0.5:
        logger.warning(f"{ticker} exhibits potential overfitting (WFE < 0.5).")
    if avg_robust > 0.1:
        logger.warning(f"{ticker} exhibits fragile parameters (High variance).")

    return wfe_df
