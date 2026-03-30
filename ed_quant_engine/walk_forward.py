import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from logger import log
from backtester import VectorizedBacktester
from data_loader import fetch_mtf_data, UNIVERSE
from features import add_features

def run_wfo(ticker: str, window_is: int = 500, window_oos: int = 125) -> pd.DataFrame:
    """
    Walk-Forward Optimization (Phase 14).
    Tests Strategy robustness by sliding an In-Sample (IS) training window
    and an Out-of-Sample (OOS) testing window across historical data.
    Evaluates Walk-Forward Efficiency (WFE).
    """
    try:
        log.info(f"Starting Walk-Forward Optimization for {ticker}...")

        # We need synchronous data fetching for WFO to avoid asyncio loop issues in scripts
        import yfinance as yf
        df = yf.download(ticker, period="5y", interval="1d", progress=False)
        if df.empty: return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
        df = df.ffill().dropna()

        df = add_features(df)
        if df.empty or len(df) < (window_is + window_oos):
            log.warning(f"Not enough data for WFO on {ticker}")
            return pd.DataFrame()

        backtester = VectorizedBacktester()
        results = []

        num_windows = (len(df) - window_is) // window_oos

        for i in range(num_windows):
            start_is = i * window_oos
            end_is = start_is + window_is
            end_oos = end_is + window_oos

            df_is = df.iloc[start_is:end_is]
            df_oos = df.iloc[end_is:end_oos]

            trades_is = backtester.run_backtest(df_is, ticker)
            trades_oos = backtester.run_backtest(df_oos, ticker)

            pnl_is = trades_is['pnl_pct'].sum() if not trades_is.empty else 0.0
            pnl_oos = trades_oos['pnl_pct'].sum() if not trades_oos.empty else 0.0

            # Annualize Returns
            ann_pnl_is = pnl_is * (252 / window_is)
            ann_pnl_oos = pnl_oos * (252 / window_oos)

            # Walk-Forward Efficiency (WFE)
            wfe = ann_pnl_oos / ann_pnl_is if ann_pnl_is > 0 else 0.0

            # Overfit Veto: If WFE < 50%, the parameter set failed to generalize
            is_overfit = wfe < 0.50

            results.append({
                "Window": i+1,
                "IS_Start": df_is.index[0].strftime('%Y-%m-%d'),
                "IS_End": df_is.index[-1].strftime('%Y-%m-%d'),
                "OOS_End": df_oos.index[-1].strftime('%Y-%m-%d'),
                "IS_PnL": pnl_is,
                "OOS_PnL": pnl_oos,
                "WFE": wfe,
                "Overfit": is_overfit
            })

        wfo_df = pd.DataFrame(results)
        log.info(f"WFO Completed for {ticker}. Avg WFE: {wfo_df['WFE'].mean():.2f}")
        return wfo_df

    except Exception as e:
        log.error(f"WFO failed for {ticker}: {e}")
        return pd.DataFrame()

