import pandas as pd
import numpy as np
from src.backtester import Backtester
from src.logger import logger
from typing import List, Dict

class WalkForwardOptimizer:
    def __init__(self, data: Dict[str, pd.DataFrame]):
        # Data should be pre-loaded and feature-engineered
        self.data = data
        self.backtester = Backtester(data) # Base instance for optimization

    def run_wfo(self, params_grid: List[Dict], is_months: int = 24, oos_months: int = 6) -> pd.DataFrame:
        """
        Runs a rolling window Walk-Forward Optimization to prevent curve-fitting.
        is_months: In-Sample training period
        oos_months: Out-Of-Sample testing period
        """
        logger.info(f"Starting WFO: IS={is_months}mo, OOS={oos_months}mo")
        results = []

        # Determine the full date range across all tickers
        all_dates = pd.DatetimeIndex([])
        for df in self.data.values():
             all_dates = all_dates.union(df.index)

        if len(all_dates) == 0:
             logger.warning("No data for WFO.")
             return pd.DataFrame()

        start_date = all_dates.min()
        end_date = all_dates.max()

        current_is_start = start_date

        while True:
            current_is_end = current_is_start + pd.DateOffset(months=is_months)
            current_oos_end = current_is_end + pd.DateOffset(months=oos_months)

            if current_oos_end > end_date:
                break # Not enough data for a full OOS window

            logger.info(f"WFO Window: IS ({current_is_start.date()} to {current_is_end.date()}), OOS ({current_is_end.date()} to {current_oos_end.date()})")

            # 1. Optimize In-Sample
            self.backtester.data = {ticker: df.loc[current_is_start:current_is_end] for ticker, df in self.data.items()}
            is_results_df = self.backtester.optimize_parameters(params_grid)

            if is_results_df.empty:
                logger.warning("Optimization yielded no trades In-Sample. Skipping window.")
                current_is_start += pd.DateOffset(months=oos_months) # Step forward
                continue

            best_params = is_results_df.iloc[0].to_dict()
            is_pnl = best_params.get('total_pnl', 0)

            # 2. Test Out-of-Sample
            self.backtester.data = {ticker: df.loc[current_is_end:current_oos_end] for ticker, df in self.data.items()}
            # Apply best params
            self.backtester.strategy.atr_sl_multiplier = best_params['sl']
            self.backtester.strategy.atr_tp_multiplier = best_params['tp']

            all_oos_trades = []
            for ticker, df in self.backtester.data.items():
                trades = self.backtester.run_backtest(ticker, df)
                all_oos_trades.extend(trades)

            oos_perf = self.backtester.evaluate_performance(all_oos_trades)
            oos_pnl = oos_perf.get('total_pnl', 0) if oos_perf else 0

            # 3. Walk-Forward Efficiency (WFE)
            # Annualized PnL approximation
            is_annualized = is_pnl * (12 / is_months) if is_months > 0 else 0
            oos_annualized = oos_pnl * (12 / oos_months) if oos_months > 0 else 0

            wfe = oos_annualized / is_annualized if is_annualized > 0 else 0

            # Reject if Overfitted
            is_overfitted = wfe < 0.50
            if is_overfitted:
                 logger.warning(f"WFO Window Failed: WFE={wfe*100:.1f}%. Strategy overfitted in this regime.")

            results.append({
                'window_start': current_is_start.date(),
                'is_end': current_is_end.date(),
                'oos_end': current_oos_end.date(),
                'best_sl': best_params['sl'],
                'best_tp': best_params['tp'],
                'is_pnl': is_pnl,
                'oos_pnl': oos_pnl,
                'wfe': wfe,
                'is_overfitted': is_overfitted
            })

            # Step forward
            current_is_start += pd.DateOffset(months=oos_months)

        return pd.DataFrame(results)

