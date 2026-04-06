import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from utils.logger import setup_logger
from strategy import generate_signals

logger = setup_logger("WalkForwardOptimizer")

def split_data_into_windows(df: pd.DataFrame, is_bars: int = 500, oos_bars: int = 100) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Splits data into In-Sample (IS) and Out-Of-Sample (OOS) rolling windows."""
    windows = []
    total_len = len(df)

    if total_len < is_bars + oos_bars:
        return windows

    start_idx = 0
    while start_idx + is_bars + oos_bars <= total_len:
        is_df = df.iloc[start_idx : start_idx + is_bars].copy()
        oos_df = df.iloc[start_idx + is_bars : start_idx + is_bars + oos_bars].copy()
        windows.append((is_df, oos_df))
        start_idx += oos_bars # Step forward by OOS length

    return windows

def test_strategy_on_window(df: pd.DataFrame, ticker: str, atr_mult: float, tp_mult: float) -> float:
    """Very basic vectorized proxy backtest for WFO testing to evaluate profitability of parameters."""
    if df.empty: return 0.0

    # We iterate row by row since strategy requires row context.
    # In a real heavy WFO this should be highly vectorized.
    signals = []
    for i in range(200, len(df)):
        # Provide history up to current row
        hist_df = df.iloc[:i]
        sig = generate_signals(hist_df, ticker, atr_mult, tp_mult)
        if sig:
            signals.append(sig)

    # Calculate crude PNL for these signals
    pnl = 0.0
    for s in signals:
        # If Long, assume we capture some TP distance or hit SL.
        # This is a proxy. A full backtester loop would be better.
        # For phase 14, we just assign theoretical expectancy.
        pnl += (s['tp_price'] - s['entry_price']) * 0.5 # Proxy 50% hit rate

    return pnl

def run_walk_forward_optimization(df: pd.DataFrame, ticker: str):
    """
    Phase 14: Walk-Forward Optimization (WFO)
    Optimizes on IS, tests on OOS. Calculates WFE.
    """
    logger.info(f"Walk-Forward Analizi Başlatılıyor: {ticker}")
    windows = split_data_into_windows(df, is_bars=500, oos_bars=100)

    if not windows:
        logger.warning("Veri seti WFO için çok kısa.")
        return

    params_to_test = [
        (1.5, 3.0),
        (2.0, 4.0),
        (1.0, 2.0)
    ]

    wfo_results = []

    for i, (is_df, oos_df) in enumerate(windows):
        best_param = None
        best_is_pnl = -np.inf

        # Optimize on IS
        for atr_mult, tp_mult in params_to_test:
            pnl = test_strategy_on_window(is_df, ticker, atr_mult, tp_mult)
            if pnl > best_is_pnl:
                best_is_pnl = pnl
                best_param = (atr_mult, tp_mult)

        # Test on OOS
        if best_param:
            oos_pnl = test_strategy_on_window(oos_df, ticker, best_param[0], best_param[1])

            # WFE Calculation: OOS PNL / IS PNL
            wfe = 0.0
            if best_is_pnl > 0:
                wfe = (oos_pnl / len(oos_df)) / (best_is_pnl / len(is_df))

            logger.info(f"Pencere {i+1}: En iyi Param={best_param}, IS PNL={best_is_pnl:.2f}, OOS PNL={oos_pnl:.2f}, WFE={wfe:.2f}")
            wfo_results.append({'Window': i, 'Param': best_param, 'IS_PNL': best_is_pnl, 'OOS_PNL': oos_pnl, 'WFE': wfe})

    df_results = pd.DataFrame(wfo_results)
    avg_wfe = df_results['WFE'].mean()

    if avg_wfe < 0.50:
        logger.warning(f"WFE skoru çok düşük ({avg_wfe:.2f} < 0.50). Sistem aşırı öğrenmiş (Overfitted) olabilir.")
    else:
        logger.info(f"WFO Başarılı. Ortalama WFE: {avg_wfe:.2f}")

if __name__ == "__main__":
    from data_loader import fetch_historical_data
    import asyncio

    async def run():
        df = await fetch_historical_data("GC=F", period="5y", interval="1d")
        if not df.empty:
            run_walk_forward_optimization(df, "GC=F")

    asyncio.run(run())
