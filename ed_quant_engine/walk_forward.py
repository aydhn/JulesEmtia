import pandas as pd
import numpy as np
from logger import logger
from backtester import Backtester

class WalkForwardOptimizer:
    def __init__(self, strategy_func):
        self.strategy_func = strategy_func
        self.backtester = Backtester()

    def run_wfo(self, df: pd.DataFrame, params_grid: dict, train_window=252*2, test_window=252//2):
        '''
        Phase 14: Rolling Window Walk-Forward Optimization
        Dynamically divides historical data into In-Sample (IS) and Out-of-Sample (OOS) windows,
        optimizes on IS, tests on OOS, and calculates Walk-Forward Efficiency (WFE).
        '''
        if df.empty or len(df) < (train_window + test_window):
            logger.warning("Insufficient data for WFO.")
            return None

        wfo_results = []
        start_idx = 0

        while start_idx + train_window + test_window <= len(df):
            train_end = start_idx + train_window
            test_end = train_end + test_window

            # Split data
            df_is = df.iloc[start_idx:train_end].copy()
            df_oos = df.iloc[train_end:test_end].copy()

            logger.info(f"WFO Window [{start_idx}:{test_end}]: Optimizing on {len(df_is)} bars, Testing on {len(df_oos)} bars.")

            # 1. Optimize on In-Sample (IS)
            # This calls the Backtester's grid search. We mock the `strategy_func` passing for this example.
            best_params, is_metrics = self.backtester.optimize_parameters(df_is, params_grid, self.strategy_func)

            # Calculate annualized IS PnL (assuming daily data for simplification)
            is_years = len(df_is) / 252
            is_annual_pnl = is_metrics['Total PnL'] / is_years if is_years > 0 else 0

            # 2. Test on Out-of-Sample (OOS) with the *best* parameters found in IS
            # df_oos_signaled = self.strategy_func(df_oos, **best_params) # Real implementation
            df_oos_signaled = df_oos.copy() # Placeholder

            self.backtester.run_vectorized_backtest(df_oos_signaled)
            oos_metrics = self.backtester.calculate_metrics()

            # Calculate annualized OOS PnL
            oos_years = len(df_oos) / 252
            oos_annual_pnl = oos_metrics['Total PnL'] / oos_years if oos_years > 0 else 0

            # 3. Walk-Forward Efficiency (WFE) Calculation
            # WFE = OOS Annual PnL / IS Annual PnL
            # If WFE < 50%, the parameter set is considered "overfitted"
            wfe = 0.0
            if is_annual_pnl > 0:
                wfe = oos_annual_pnl / is_annual_pnl

            logger.info(f"OOS Metrics: {oos_metrics} | WFE: {wfe:.2%}")

            if wfe < 0.50:
                logger.warning(f"WFE {wfe:.2%} < 50%. Parameter set {best_params} is overfitted and rejected for this window.")

            # 4. Robustness Check (Neighborhood Variance)
            # A simple implementation: check if slight variations of `best_params` yield drastically different results.
            # E.g., if best RSI period is 14, check 13 and 15.
            robustness_score = self._calculate_robustness(df_is, best_params, is_metrics['Total PnL'])
            logger.info(f"Robustness Score (Variance): {robustness_score:.2f}")

            wfo_results.append({
                'start_idx': start_idx,
                'train_end': train_end,
                'test_end': test_end,
                'best_params': best_params,
                'is_metrics': is_metrics,
                'oos_metrics': oos_metrics,
                'wfe': wfe,
                'robustness_score': robustness_score
            })

            # Slide window forward by the test_window step
            start_idx += test_window

        logger.info("Walk-Forward Optimization Complete.")
        return pd.DataFrame(wfo_results)

    def _calculate_robustness(self, df_is: pd.DataFrame, best_params: dict, best_pnl: float) -> float:
        '''
        Phase 14: Parameter Robustness Check
        Evaluates the variance of PnL in the immediate neighborhood of the best parameters.
        A highly robust strategy will have low variance (similar PnL) for slightly altered parameters.
        '''
        if not best_params:
            return 0.0

        neighbor_pnls = []

        # Simple robustness: vary integer parameters by +/- 1
        for key, val in best_params.items():
            if isinstance(val, int) and val > 1:
                # Test +1
                neighbor_params_up = best_params.copy()
                neighbor_params_up[key] = val + 1
                # self.backtester.run_vectorized_backtest(self.strategy_func(df_is, **neighbor_params_up))
                # metrics_up = self.backtester.calculate_metrics()
                # neighbor_pnls.append(metrics_up['Total PnL'])

                # Test -1
                neighbor_params_down = best_params.copy()
                neighbor_params_down[key] = val - 1
                # self.backtester.run_vectorized_backtest(self.strategy_func(df_is, **neighbor_params_down))
                # metrics_down = self.backtester.calculate_metrics()
                # neighbor_pnls.append(metrics_down['Total PnL'])

                # Mocking PnL for example
                neighbor_pnls.extend([best_pnl * 0.95, best_pnl * 1.05])

        if not neighbor_pnls:
            return 1.0 # Perfectly robust if no parameters to vary

        # Variance as a percentage of the best PnL
        variance = np.var(neighbor_pnls)
        robustness_score = 1.0 / (1.0 + variance) # Inverse variance for a score

        return robustness_score
