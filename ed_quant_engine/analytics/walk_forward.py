import pandas as pd
from analytics.backtester import run_backtest

def walk_forward_optimization(df: pd.DataFrame, window_size=252*2, step_size=252//2):
    # e.g., 2 years train, 6 months test
    wfe_scores = []

    for start in range(0, len(df) - window_size - step_size, step_size):
        end_is = start + window_size
        end_oos = end_is + step_size

        df_is = df.iloc[start:end_is]
        df_oos = df.iloc[end_is:end_oos]

        res_is = run_backtest(df_is)
        res_oos = run_backtest(df_oos)

        if res_is and res_oos and res_is['Final_Balance'] > 0:
            wfe = res_oos['Final_Balance'] / res_is['Final_Balance']
            wfe_scores.append(wfe)

    avg_wfe = sum(wfe_scores) / len(wfe_scores) if wfe_scores else 0
    return avg_wfe
