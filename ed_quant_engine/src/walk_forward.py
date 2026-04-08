import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from concurrent.futures import ProcessPoolExecutor

logger = logging.getLogger(__name__)

class WalkForwardOptimizer:
    """
    Phase 14: Walk-Forward Analysis and Out-of-Sample Testing
    """
    def __init__(self, is_window_size: int = 500, oos_window_size: int = 125, min_wfe: float = 0.5):
        # Default roughly 2 years In-Sample (IS), 6 months Out-Of-Sample (OOS)
        self.is_window_size = is_window_size
        self.oos_window_size = oos_window_size
        self.min_wfe = min_wfe

    def run_backtest_vectorized(self, mtf_df: pd.DataFrame, params: dict) -> float:
        """
        Fast vectorized backtest simulation for specific parameters.
        Returns total PnL percentage.
        Includes 0.1% slippage and 0.05% commission per trade.
        """
        if mtf_df.empty or len(mtf_df) < 2:
            return 0.0

        df = mtf_df.copy()

        # Extract params
        rsi_oversold = params.get('rsi_oversold', 35)
        rsi_overbought = params.get('rsi_overbought', 65)
        atr_sl_mult = params.get('atr_sl_mult', 1.5)
        atr_tp_mult = params.get('atr_tp_mult', 3.0)

        # Check required columns
        req_cols = ['Close', 'EMA_50', 'Close_HTF', 'EMA_50_HTF', 'ATR_14']
        missing_cols = [c for c in req_cols if c not in df.columns]
        if missing_cols:
            return 0.0

        # Determine columns dynamically for flexibility
        macd_htf_col = next((c for c in df.columns if c.startswith('MACDh_') and c.endswith('_HTF')), None)
        macd_ltf_col = next((c for c in df.columns if c.startswith('MACDh_') and not c.endswith('_HTF')), None)
        rsi_col = next((c for c in df.columns if c.startswith('RSI_')), None)

        # Simplified vector strategy (mirrors strategy.py logic)
        # Shift values by 1 to prevent lookahead bias
        prev = df.shift(1)

        # HTF trend
        htf_bull = (prev['Close_HTF'] > prev['EMA_50_HTF'])
        htf_bear = (prev['Close_HTF'] < prev['EMA_50_HTF'])
        if macd_htf_col:
            htf_bull &= (prev[macd_htf_col] > 0)
            htf_bear &= (prev[macd_htf_col] < 0)

        # LTF trigger
        ltf_bull = (prev['Close'] > prev['EMA_50'])
        ltf_bear = (prev['Close'] < prev['EMA_50'])

        if rsi_col:
            ltf_bull &= (prev[rsi_col] < rsi_oversold)
            ltf_bear &= (prev[rsi_col] > rsi_overbought)

        if macd_ltf_col:
            ltf_bull |= (prev[macd_ltf_col] > 0)
            ltf_bear |= (prev[macd_ltf_col] < 0)

        # Signals
        long_signals = htf_bull & ltf_bull
        short_signals = htf_bear & ltf_bear

        # Initialize tracking arrays
        entries = np.zeros(len(df))
        directions = np.zeros(len(df)) # 1 for Long, -1 for Short

        entries[long_signals] = df['Open'][long_signals]
        directions[long_signals] = 1

        entries[short_signals] = df['Open'][short_signals]
        directions[short_signals] = -1

        # Calculate PnL (Simplified vectorized execution)
        # We assume holding period of 1 candle for fast approximation,
        # or fixed TP/SL hit using high/low.
        # This is a highly simplified proxy backtest to gauge robustness quickly

        pnl = 0.0
        slippage_pct = 0.0010  # 0.1%
        commission_pct = 0.0005 # 0.05%

        for i in range(1, len(df)):
            if directions[i] != 0:
                entry = entries[i]
                direction = directions[i]
                atr = df['ATR_14'].iloc[i-1]

                # Assume trade closes at the end of the next bar for simple approx,
                # or checks High/Low for TP/SL hit
                high = df['High'].iloc[i]
                low = df['Low'].iloc[i]
                close = df['Close'].iloc[i]

                sl_dist = atr_sl_mult * atr
                tp_dist = atr_tp_mult * atr

                if direction == 1:
                    if low <= entry - sl_dist:
                        exit_price = entry - sl_dist
                    elif high >= entry + tp_dist:
                        exit_price = entry + tp_dist
                    else:
                        exit_price = close

                    raw_pnl_pct = (exit_price - entry) / entry

                else:
                    if high >= entry + sl_dist:
                        exit_price = entry + sl_dist
                    elif low <= entry - tp_dist:
                        exit_price = entry - tp_dist
                    else:
                        exit_price = close

                    raw_pnl_pct = (entry - exit_price) / entry

                # Apply costs: Slippage on entry and exit (2x) + Commission
                net_pnl_pct = raw_pnl_pct - (2 * slippage_pct) - (2 * commission_pct)
                pnl += net_pnl_pct

        return pnl

    def calculate_robustness(self, mtf_df: pd.DataFrame, best_params: dict, param_grid: List[dict]) -> float:
        """
        Calculates parameter robustness by testing neighborhood variance.
        """
        # Find neighbors (e.g. RSI 30 +/- 5)
        neighbors = []
        for p in param_grid:
            # Simple heuristic to find "close" parameters
            rsi_diff = abs(p.get('rsi_oversold', 35) - best_params.get('rsi_oversold', 35))
            if rsi_diff <= 5 and p != best_params:
                neighbors.append(p)

        if not neighbors:
            return 1.0 # Max robust if no neighbors to compare

        neighbor_pnls = [self.run_backtest_vectorized(mtf_df, p) for p in neighbors]
        best_pnl = self.run_backtest_vectorized(mtf_df, best_params)

        if best_pnl <= 0:
            return 0.0

        avg_neighbor_pnl = np.mean(neighbor_pnls)

        # Robustness score: How much of the best performance is retained by neighbors
        robustness_score = max(0.0, min(1.0, avg_neighbor_pnl / best_pnl))
        return robustness_score

    def wfo_iteration(self, data: pd.DataFrame, is_start: int, param_grid: List[dict]) -> dict:
        is_end = is_start + self.is_window_size
        oos_end = is_end + self.oos_window_size

        if oos_end > len(data):
            return {}

        is_data = data.iloc[is_start:is_end]
        oos_data = data.iloc[is_end:oos_end]

        best_is_pnl = -np.inf
        best_params = None

        for params in param_grid:
            pnl = self.run_backtest_vectorized(is_data, params)
            if pnl > best_is_pnl:
                best_is_pnl = pnl
                best_params = params

        # Test best params on OOS
        if best_params is not None:
            oos_pnl = self.run_backtest_vectorized(oos_data, best_params)

            # WFE (Walk Forward Efficiency)
            is_annualized = (best_is_pnl / self.is_window_size) * 252 if self.is_window_size > 0 else 0
            oos_annualized = (oos_pnl / self.oos_window_size) * 252 if self.oos_window_size > 0 else 0

            wfe = oos_annualized / is_annualized if is_annualized > 0 else 0
            robust = True if wfe >= self.min_wfe else False

            # Neighborhood robustness score
            robustness_score = self.calculate_robustness(is_data, best_params, param_grid)

            # Final acceptance: Must be efficient out of sample AND robust to small parameter changes
            if robustness_score < 0.6:
                robust = False

            return {
                "window_start": data.index[is_start],
                "window_end": data.index[is_end],
                "params": best_params,
                "is_pnl": best_is_pnl,
                "oos_pnl": oos_pnl,
                "wfe": wfe,
                "robustness_score": robustness_score,
                "robust": robust
            }
        return {}

    def run_optimization(self, data: pd.DataFrame, param_grid: List[dict]) -> pd.DataFrame:
        """
        Runs Walk-Forward Optimization using parallel processing to save CPU time.
        """
        logger.info("Starting Walk-Forward Optimization...")
        results = []

        starts = range(0, len(data) - self.is_window_size - self.oos_window_size + 1, self.oos_window_size)

        # CPU-friendly parallel execution
        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(self.wfo_iteration, data, start, param_grid) for start in starts]
            for future in futures:
                res = future.result()
                if res:
                    results.append(res)

        df_results = pd.DataFrame(results)

        if not df_results.empty:
            robust_sets = df_results[df_results['robust'] == True]
            logger.info(f"WFO completed. Found {len(robust_sets)} robust windows out of {len(df_results)}.")

        return df_results
