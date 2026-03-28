import pandas as pd
from backtester import Backtester

# Phase 14: Walk-Forward Optimization & Out-of-Sample Testing
class WalkForwardOptimization:
    def __init__(self, data: pd.DataFrame, is_window_months=24, oos_window_months=6):
        self.data = data.sort_index()
        self.is_months = is_window_months
        self.oos_months = oos_window_months

    def _split_data(self):
        windows = []
        start_date = self.data.index[0]
        end_date = self.data.index[-1]

        current_is_start = start_date

        while True:
            current_is_end = current_is_start + pd.DateOffset(months=self.is_months)
            current_oos_end = current_is_end + pd.DateOffset(months=self.oos_months)

            if current_oos_end > end_date:
                break

            is_data = self.data.loc[current_is_start:current_is_end]
            oos_data = self.data.loc[current_is_end:current_oos_end]

            windows.append({'IS': is_data, 'OOS': oos_data})

            current_is_start += pd.DateOffset(months=self.oos_months) # Step forward

        return windows

    def execute_wfo(self) -> pd.DataFrame:
        windows = self._split_data()
        results = []

        for idx, window in enumerate(windows):
            is_tester = Backtester(window['IS'])
            is_result = is_tester.run_backtest()

            oos_tester = Backtester(window['OOS'])
            oos_result = oos_tester.run_backtest()

            is_ann_return = is_result['Total_PnL'] / (self.is_months / 12.0) if self.is_months > 0 else 0
            oos_ann_return = oos_result['Total_PnL'] / (self.oos_months / 12.0) if self.oos_months > 0 else 0

            # WFE: Walk Forward Efficiency
            wfe = (oos_ann_return / is_ann_return) * 100 if is_ann_return > 0 else 0

            status = "Approved" if wfe > 50 else "Rejected (Overfitted)"

            results.append({
                "Window": idx + 1,
                "IS_PnL": is_result['Total_PnL'],
                "OOS_PnL": oos_result['Total_PnL'],
                "IS_WinRate": is_result['Win_Rate'],
                "OOS_WinRate": oos_result['Win_Rate'],
                "WFE (%)": wfe,
                "Status": status
            })

        return pd.DataFrame(results)
