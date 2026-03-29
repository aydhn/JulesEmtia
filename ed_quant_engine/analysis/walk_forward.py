import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from ed_quant_engine.core.logger import logger
from ed_quant_engine.strategy.strategy import MovingAverageCrossStrategy

def execute_wfo_iteration(train_data: pd.DataFrame, test_data: pd.DataFrame, params: Dict) -> Tuple[float, float, float]:
    """
    Executes a single Walk-Forward Optimization (WFO) window.
    Evaluates In-Sample (IS) and Out-of-Sample (OOS) performance.
    """
    # 1. Instantiate Strategy with given params
    strategy = MovingAverageCrossStrategy(
        atr_multiplier_sl=params['sl_atr'],
        atr_multiplier_tp=params['tp_atr'],
        risk_reward_ratio=params['tp_atr']/params['sl_atr']
    )

    # 2. In-Sample Training (IS)
    is_signals = strategy.generate_signals(train_data)
    is_pnl = calculate_vectorized_pnl(is_signals, params)

    # 3. Out-of-Sample Testing (OOS)
    oos_signals = strategy.generate_signals(test_data)
    oos_pnl = calculate_vectorized_pnl(oos_signals, params)

    # Calculate WFE (Walk Forward Efficiency)
    # WFE = OOS Annualized Return / IS Annualized Return
    # Using simple PnL ratio here for speed
    if is_pnl > 0:
        wfe = (oos_pnl / is_pnl) * 100
    else:
        wfe = 0.0

    return is_pnl, oos_pnl, wfe

def calculate_vectorized_pnl(df: pd.DataFrame, params: Dict) -> float:
    """
    Lightning fast vectorized PnL approximation for WFO.
    Avoids slow loops. Uses simple entry-to-close metrics.
    """
    if 'signal' not in df.columns:
        return 0.0

    data = df.copy()

    # Identify entries
    long_entries = data[data['signal'] == 1]
    short_entries = data[data['signal'] == -1]

    if long_entries.empty and short_entries.empty:
        return 0.0

    # Simplified PnL: Close price 5 periods later minus Entry price
    # In reality, this requires a complex event-driven simulator.
    # We use a fast vectorized approximation for grid search.
    # We shift future prices back to the entry row
    data['future_close'] = data['close'].shift(-5)

    long_pnl = (data.loc[long_entries.index, 'future_close'] - data.loc[long_entries.index, 'open']).sum()
    short_pnl = (data.loc[short_entries.index, 'open'] - data.loc[short_entries.index, 'future_close']).sum()

    # Deduct Slippage/Commission
    total_trades = len(long_entries) + len(short_entries)
    cost = total_trades * 0.001 * data['close'].mean() # Fixed 0.1% cost proxy

    return (long_pnl + short_pnl) - cost

def run_wfo(df: pd.DataFrame, window_size: int = 500, test_size: int = 100) -> pd.DataFrame:
    """
    Walk-Forward Optimization Engine.
    Slides a training/testing window over historical data.
    """
    logger.info("Starting Walk-Forward Optimization (WFO)...")
    results = []

    # Grid of parameters to test
    param_grid = [
        {'sl_atr': 1.0, 'tp_atr': 2.0},
        {'sl_atr': 1.5, 'tp_atr': 3.0},
        {'sl_atr': 2.0, 'tp_atr': 4.0}
    ]

    if len(df) < window_size + test_size:
        logger.error("Not enough data for WFO.")
        return pd.DataFrame()

    # Slide Window
    start_idx = 0
    iteration = 1

    while start_idx + window_size + test_size <= len(df):
        train = df.iloc[start_idx : start_idx + window_size]
        test = df.iloc[start_idx + window_size : start_idx + window_size + test_size]

        best_wfe = -1.0
        best_params = None

        for params in param_grid:
            is_pnl, oos_pnl, wfe = execute_wfo_iteration(train, test, params)

            # Record iteration details
            results.append({
                'Iteration': iteration,
                'Params': f"{params['sl_atr']}-{params['tp_atr']}",
                'IS_PnL': is_pnl,
                'OOS_PnL': oos_pnl,
                'WFE (%)': wfe
            })

            # Robustness Check: Reject if WFE < 50% (Overfitted)
            if wfe < 50.0:
                logger.debug(f"WFO Iteration {iteration}: Params {params} OVERFITTED (WFE {wfe:.1f}%)")
            else:
                logger.debug(f"WFO Iteration {iteration}: Params {params} PASSED (WFE {wfe:.1f}%)")

        start_idx += test_size # Slide forward by test size
        iteration += 1

    results_df = pd.DataFrame(results)
    logger.info(f"WFO Complete. {len(results_df)} parameter sets tested across {iteration-1} windows.")
    return results_df
