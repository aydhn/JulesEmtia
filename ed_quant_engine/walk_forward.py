import pandas as pd
import numpy as np
from typing import Dict, Any, List
from backtester import VectorizedBacktester
from logger import logger

class WalkForwardOptimizer:
    """
    Phase 14: Walk-Forward Optimization (WFO) Engine.
    Prevents Overfitting (Curve Fitting) by slicing data into In-Sample (IS) and Out-of-Sample (OOS) windows.
    Zero-budget rolling window analysis.
    """

    @classmethod
    def run_wfo(cls, ticker: str, daily_df: pd.DataFrame, hourly_df: pd.DataFrame, is_months: int = 24, oos_months: int = 6) -> pd.DataFrame:
        """
        Executes a Walk-Forward Optimization routine on a given asset.
        Slices the historical data into rolling windows.
        is_months: In-Sample training period (e.g. 24 months)
        oos_months: Out-of-Sample testing period (e.g. 6 months)
        Returns a DataFrame summarizing WFE (Walk-Forward Efficiency) for each window.
        """
        if hourly_df.empty or daily_df.empty:
            logger.warning(f"Insufficient data for WFO on {ticker}.")
            return pd.DataFrame()

        # Ensure index is datetime
        hourly_df.index = pd.to_datetime(hourly_df.index)
        daily_df.index = pd.to_datetime(daily_df.index)

        start_date = hourly_df.index.min()
        end_date = hourly_df.index.max()

        # Calculate window size in days
        is_days = is_months * 30
        oos_days = oos_months * 30

        results = []

        current_start = start_date
        window_idx = 1

        while True:
            is_end = current_start + pd.Timedelta(days=is_days)
            oos_end = is_end + pd.Timedelta(days=oos_days)

            if oos_end > end_date:
                break # We've reached the end of our dataset

            # Slice the data
            is_hourly = hourly_df[(hourly_df.index >= current_start) & (hourly_df.index < is_end)]
            is_daily = daily_df[(daily_df.index >= current_start) & (daily_df.index < is_end)]

            oos_hourly = hourly_df[(hourly_df.index >= is_end) & (hourly_df.index < oos_end)]
            oos_daily = daily_df[(daily_df.index >= is_end) & (daily_df.index < oos_end)]

            logger.info(f"Running WFO Window {window_idx}: IS ({current_start.date()} to {is_end.date()}), OOS ({is_end.date()} to {oos_end.date()})")

            # Run Backtests
            is_trades = VectorizedBacktester.run_backtest(ticker, is_daily, is_hourly)
            oos_trades = VectorizedBacktester.run_backtest(ticker, oos_daily, oos_hourly)

            is_metrics = VectorizedBacktester.analyze_results(is_trades)
            oos_metrics = VectorizedBacktester.analyze_results(oos_trades)

            # Calculate Walk-Forward Efficiency (WFE)
            # WFE = Annualized OOS Profit / Annualized IS Profit
            is_annual_pnl = is_metrics['Total PnL'] / (is_months / 12.0) if is_months > 0 else 0
            oos_annual_pnl = oos_metrics['Total PnL'] / (oos_months / 12.0) if oos_months > 0 else 0

            wfe = 0.0
            if is_annual_pnl > 0:
                wfe = (oos_annual_pnl / is_annual_pnl) * 100.0

            # Robustness Check (Is WFE > 50%?)
            is_robust = wfe >= 50.0 and oos_metrics['Total PnL'] > 0

            results.append({
                'Window': window_idx,
                'IS_Start': current_start.date(),
                'IS_End': is_end.date(),
                'OOS_Start': is_end.date(),
                'OOS_End': oos_end.date(),
                'IS_PnL': is_metrics['Total PnL'],
                'IS_WinRate': is_metrics['Win Rate'],
                'OOS_PnL': oos_metrics['Total PnL'],
                'OOS_WinRate': oos_metrics['Win Rate'],
                'WFE_Pct': wfe,
                'Robust': is_robust
            })

            # Step forward by OOS months for the next window
            current_start += pd.Timedelta(days=oos_days)
            window_idx += 1

        wfo_df = pd.DataFrame(results)

        # Log Summary
        if not wfo_df.empty:
            robust_pct = (wfo_df['Robust'].sum() / len(wfo_df)) * 100
            logger.info(f"WFO Complete for {ticker}. Overall Robustness: {robust_pct:.1f}%")
            if robust_pct < 50.0:
                logger.warning(f"{ticker} Strategy is highly overfitted. Failed WFO.")

        return wfo_df

