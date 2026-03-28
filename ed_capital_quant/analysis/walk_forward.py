import pandas as pd
import numpy as np
from typing import Dict, Any

from core.logger import logger
from analysis.backtester import Backtester

class WalkForwardOptimizer:
    """Walk-Forward Optimization (WFO) motoru. Gelecekteki başarısını garantilemek için Overfitting (Aşırı Öğrenme) koruması sağlar."""

    def __init__(self, is_window: int = 24, os_window: int = 6):
        self.is_window = is_window # In-Sample penceresi (Eğitim) Örn: 24 Ay
        self.os_window = os_window # Out-of-Sample penceresi (Test) Örn: 6 Ay
        self.backtester = Backtester()

    def run_wfo(self, df_htf: pd.DataFrame, df_ltf: pd.DataFrame, ticker: str, param_grid: dict) -> pd.DataFrame:
        """Geçmiş veriyi kayan pencereler (Rolling Window) ile böler. In-Sample optimizasyonu yapar, Out-of-Sample ile test eder."""
        if len(df_ltf) < (self.is_window + self.os_window) * 20 * 24: # Yaklaşık iş günü saati hesabı
            logger.warning("WFO için yetersiz veri. Minimum %d saatlik veri gerekli.", (self.is_window + self.os_window) * 480)
            return pd.DataFrame()

        logger.info(f"Walk-Forward Optimization başlatıldı: {ticker}")

        # Basit bir zaman dilimi ayrımı yap
        total_months = (df_ltf.index[-1] - df_ltf.index[0]).days // 30
        num_windows = (total_months - self.is_window) // self.os_window

        results = []
        for i in range(num_windows):
            start_is = df_ltf.index[0] + pd.DateOffset(months=i*self.os_window)
            end_is = start_is + pd.DateOffset(months=self.is_window)
            end_os = end_is + pd.DateOffset(months=self.os_window)

            # Veri Filtreleme
            is_df_ltf = df_ltf[(df_ltf.index >= start_is) & (df_ltf.index < end_is)]
            os_df_ltf = df_ltf[(df_ltf.index >= end_is) & (df_ltf.index < end_os)]

            is_df_htf = df_htf[df_htf.index < end_is]
            os_df_htf = df_htf[df_htf.index < end_os]

            # 1. In-Sample Optimizasyon (Eğitim Dönemi)
            is_results = self.backtester.grid_search(ticker, is_df_htf, is_df_ltf, param_grid)
            if is_results.empty:
                continue

            # En iyi parametreyi seç (Profit Factor'ü en yüksek olan)
            best_params = is_results.iloc[0].to_dict()
            is_profit_factor = best_params['Profit Factor']
            is_win_rate = best_params['Win Rate']
            is_pnl = best_params['Total PnL']

            # Optimizasyon parametrelerini ayıkla (Sonuç metrikleri hariç)
            test_params = {k: v for k, v in best_params.items() if k not in ['Total Trades', 'Win Rate', 'Profit Factor', 'Total PnL']}

            # 2. Out-of-Sample Testi (Hiç Görülmemiş Veri ile)
            os_result = self.backtester.run_backtest(os_df_htf, os_df_ltf, ticker, test_params)

            os_profit_factor = os_result['Profit Factor']
            os_win_rate = os_result['Win Rate']
            os_pnl = os_result['Total PnL']

            # Walk-Forward Efficiency (WFE) = Yıllıklandırılmış OOS Kârı / Yıllıklandırılmış IS Kârı
            # Dönemleri aya bölerek yıllıklandır:
            is_annual_pnl = (is_pnl / self.is_window) * 12
            os_annual_pnl = (os_pnl / self.os_window) * 12

            wfe = (os_annual_pnl / is_annual_pnl) if is_annual_pnl > 0 else 0

            is_overfitted = wfe < 0.50 # WFE %50'den düşükse sistem OOS'de (gerçek testte) batırmıştır.

            res = {
                "Window": i+1,
                "Start": start_is.strftime('%Y-%m'),
                "IS End": end_is.strftime('%Y-%m'),
                "OS End": end_os.strftime('%Y-%m'),
                "IS Profit Factor": is_profit_factor,
                "IS Win Rate": is_win_rate,
                "OS Profit Factor": os_profit_factor,
                "OS Win Rate": os_win_rate,
                "WFE": wfe,
                "Overfitted": is_overfitted
            }
            res.update(test_params)
            results.append(res)

        df_wfo = pd.DataFrame(results)

        # Ortalama WFE değeri
        avg_wfe = df_wfo['WFE'].mean()
        logger.info(f"[{ticker}] WFO Tamamlandı. Ortalama Verimlilik (WFE): {avg_wfe:.2f}")

        if avg_wfe < 0.50:
            logger.warning(f"[{ticker}] Strateji geçmişi EZBERLEMİŞTİR (Curve Fitting). Canlıya alınması risklidir.")
        else:
            logger.info(f"[{ticker}] Strateji Dayanıklıdır (Robust). OOS Testlerini geçmiştir.")

        return df_wfo