import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from .backtester import run_vectorized_backtest
from .logger import log_info, log_error, log_warning

def walk_forward_optimization(df: pd.DataFrame, direction: str, is_window: int = 2000, oos_window: int = 500) -> Dict:
    """
    ED Capital Standartlarında Walk-Forward Optimization (WFO) Motoru.
    Geçmiş verileri yuvarlanan pencerelere (Rolling Windows) böler:
    - In-Sample (IS): Optimizasyon yapılan eğitim seti (Örn: 2000 saatlik mum).
    - Out-of-Sample (OOS): Modelin test edildiği görülmemiş set (Örn: 500 saatlik mum).

    Amacı: Stratejinin aşırı uymasını (Overfitting) test etmek ve Walk-Forward Efficiency (WFE) ölçmek.
    """
    if df is None or len(df) < (is_window + oos_window):
        log_error("WFO için yeterli veri yok.")
        return {}

    log_info(f"Walk-Forward Optimization Başladı ({direction} Yönlü)...")

    # Strateji Parametre Uzayı (Grid) - CPU Dostu olması için dar tutulmuştur.
    # Örn: (sl_multiplier, tp_multiplier)
    param_grid = [
        (1.0, 2.0),
        (1.5, 3.0),
        (2.0, 4.0),
        (1.5, 2.0)
    ]

    total_length = len(df)
    results = []

    # Pencereyi Kaydırma (Walk Forward)
    start_idx = 0
    while start_idx + is_window + oos_window <= total_length:
        is_df = df.iloc[start_idx : start_idx + is_window]
        oos_df = df.iloc[start_idx + is_window : start_idx + is_window + oos_window]

        # In-Sample Optimizasyonu
        best_is_pnl = -float('inf')
        best_params = None

        for params in param_grid:
            sl_mult, tp_mult = params
            res = run_vectorized_backtest(is_df, direction, sl_mult, tp_mult)
            if res['NetPnL'] > best_is_pnl:
                best_is_pnl = res['NetPnL']
                best_params = params

        # Bulunan en iyi IS parametreleriyle OOS testi yap
        if best_params:
            sl_mult, tp_mult = best_params
            oos_res = run_vectorized_backtest(oos_df, direction, sl_mult, tp_mult)

            # Yıllıklandırma veya oranlama
            is_annualized_pnl = (best_is_pnl / is_window) * 8760 # Varsayımsal saat
            oos_annualized_pnl = (oos_res['NetPnL'] / oos_window) * 8760

            # Walk-Forward Efficiency (WFE) Hesaplama
            # Eğer IS Kârı > 0 ise hesapla
            if is_annualized_pnl > 0:
                wfe = (oos_annualized_pnl / is_annualized_pnl) * 100
            else:
                wfe = 0

            results.append({
                "IS_Start": is_df.index[0],
                "OOS_End": oos_df.index[-1],
                "Best_Params": best_params,
                "IS_PnL": best_is_pnl,
                "OOS_PnL": oos_res['NetPnL'],
                "WFE_Pct": wfe
            })

        start_idx += oos_window

    if not results:
        return {}

    # Genel Değerlendirme
    df_results = pd.DataFrame(results)
    avg_wfe = df_results['WFE_Pct'].mean()

    log_info(f"WFO Tamamlandı. Ortalama Walk-Forward Efficiency (WFE): %{avg_wfe:.2f}")

    if avg_wfe < 50.0:
        log_warning("🚨 WFO UYARISI: Ortalama WFE %50'nin altında. Strateji yüksek oranda OVERFITTED (Ezberlenmiş) olabilir!")
    else:
        log_info("✅ WFO ONAYI: Strateji sağlam görünüyor (Robust).")

    return {
        "Avg_WFE": avg_wfe,
        "Total_Periods": len(results),
        "Details": results
    }
