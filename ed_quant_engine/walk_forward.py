import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_loader import fetch_historical_data
from backtester import run_historical_backtest
from logger import setup_logger

logger = setup_logger("WalkForward")

def run_walk_forward_optimization(ticker: str, start_date: str = "2018-01-01", is_window_months: int = 24, oos_window_months: int = 6):
    """Executes a Walk-Forward Optimization (WFO) to test parameter robustness and avoid curve-fitting."""
    logger.info(f"Walk-Forward Optimizasyonu Başlatılıyor [{ticker}] (IS: {is_window_months} Ay, OOS: {oos_window_months} Ay)")

    # Normally WFO involves optimizing parameters over IS and testing over OOS.
    # Since our strategy parameters are fixed for simplicity in this skeleton,
    # we will just calculate the Walk-Forward Efficiency (WFE) of our core strategy across rolling windows.

    # Convert dates
    current_start = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_dt = datetime.now() - timedelta(days=30) # Stop testing a month ago

    results = []

    while True:
        # Calculate In-Sample End
        is_end = current_start + timedelta(days=is_window_months*30)

        # Calculate Out-of-Sample End
        oos_end = is_end + timedelta(days=oos_window_months*30)

        if oos_end > end_date_dt:
            break # Stop if we run out of data

        is_start_str = current_start.strftime("%Y-%m-%d")
        is_end_str = is_end.strftime("%Y-%m-%d")
        oos_end_str = oos_end.strftime("%Y-%m-%d")

        logger.info(f"Pencere Çalıştırılıyor: IS [{is_start_str} -> {is_end_str}], OOS [{is_end_str} -> {oos_end_str}]")

        # Run Backtest over IS
        is_results = run_historical_backtest(ticker, start_date=is_start_str, end_date=is_end_str)
        if not is_results:
            current_start += timedelta(days=oos_window_months*30) # Slide window forward
            continue

        # Run Backtest over OOS
        oos_results = run_historical_backtest(ticker, start_date=is_end_str, end_date=oos_end_str)
        if not oos_results:
            current_start += timedelta(days=oos_window_months*30)
            continue

        # Calculate Annualized PnL to normalize comparison
        is_ann_pnl = is_results['net_pnl'] / (is_window_months / 12)
        oos_ann_pnl = oos_results['net_pnl'] / (oos_window_months / 12)

        # Walk-Forward Efficiency (WFE)
        # Ratio of OOS Annualized Return to IS Annualized Return
        wfe = (oos_ann_pnl / is_ann_pnl) * 100 if is_ann_pnl > 0 else 0

        is_overfitted = wfe < 50.0 # If OOS performance is less than 50% of IS, strategy is likely overfit.

        logger.info(f"WFO Sonuç: IS PnL(Yıllık): ${is_ann_pnl:.2f} | OOS PnL(Yıllık): ${oos_ann_pnl:.2f} | WFE: %{wfe:.2f} | Overfit: {is_overfitted}")

        results.append({
            "is_start": is_start_str,
            "is_end": is_end_str,
            "oos_end": oos_end_str,
            "is_ann_pnl": is_ann_pnl,
            "oos_ann_pnl": oos_ann_pnl,
            "wfe": wfe,
            "overfitted": is_overfitted
        })

        # Slide Window
        current_start += timedelta(days=oos_window_months*30)

    # Summarize Robustness
    df_res = pd.DataFrame(results)
    if not df_res.empty:
        avg_wfe = df_res['wfe'].mean()
        overfit_count = df_res['overfitted'].sum()
        total_windows = len(df_res)

        logger.info(f"WFO Özeti [{ticker}]: Ortalama WFE: %{avg_wfe:.2f} | Pencereler: {total_windows} | Ezberlenmiş: {overfit_count}/{total_windows}")

        if avg_wfe < 50 or overfit_count > (total_windows / 2):
            logger.critical(f"STRATEJİ DAYANIKLILIK TESTİNDEN KALDI [{ticker}]. Parametreler Overfit (Ezber). Canlıya alınmamalıdır.")
        else:
            logger.info(f"STRATEJİ DAYANIKLILIK TESTİNİ GEÇTİ [{ticker}]. WFE skorları başarılı.")

    return results
