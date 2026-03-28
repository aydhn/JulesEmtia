import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.core.paper_db import get_closed_trades
from src.core.logger import logger
import os

class Reporter:
    @staticmethod
    def generate_tear_sheet(filename="logs/ED_Capital_Tear_Sheet.html"):
        """
        Generates ED Capital Corporate Template HTML Report.
        """
        try:
            trades = get_closed_trades()
            if not trades:
                logger.warning("No closed trades to report.")
                return None

            df = pd.DataFrame(trades)
            df['pnl'] = df['pnl'].astype(float)
            df['entry_time'] = pd.to_datetime(df['entry_time'])

            # Metrics
            total_pnl = df['pnl'].sum()
            win_trades = df[df['pnl'] > 0]
            loss_trades = df[df['pnl'] <= 0]

            win_rate = len(win_trades) / len(df) * 100
            gross_profit = win_trades['pnl'].sum()
            gross_loss = abs(loss_trades['pnl'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

            avg_win = win_trades['pnl'].mean() if len(win_trades) > 0 else 0
            avg_loss = loss_trades['pnl'].mean() if len(loss_trades) > 0 else 0

            # Cumulative Equity
            initial_cap = 10000.0
            df['cumulative_pnl'] = df['pnl'].cumsum() + initial_cap

            max_drawdown = 0.0
            peak = initial_cap

            for eq in df['cumulative_pnl']:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100
                if dd > max_drawdown:
                    max_drawdown = dd

            # Monte Carlo (Fast)
            mc_runs = 10000
            pnl_array = df['pnl'].values
            if len(pnl_array) > 10:
                simulations = np.random.choice(pnl_array, (mc_runs, len(pnl_array)), replace=True)
                cumulative_sims = np.cumsum(simulations, axis=1)
                final_equities = cumulative_sims[:, -1]
                risk_of_ruin = np.mean(final_equities <= - (initial_cap * 0.5)) * 100 # Risk of losing 50%
            else:
                risk_of_ruin = "N/A (Yetersiz Veri)"


            # USD/TRY Benchmark
            benchmark_return = "N/A"
            try:
                start_date = df['entry_time'].min().strftime('%Y-%m-%d')
                usdtry = yf.download("USDTRY=X", start=start_date, progress=False)
                if not usdtry.empty:
                    start_price = usdtry['Close'].iloc[0].item()
                    end_price = usdtry['Close'].iloc[-1].item()
                    benchmark_return = f"{((end_price - start_price) / start_price * 100):.2f}%"
            except Exception as e:
                logger.warning(f"Failed to fetch USD/TRY benchmark: {e}")

            # HTML Template

            html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; }}
                    h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
                    h2 {{ color: #2d3748; }}
                    .metric {{ font-size: 1.2em; margin-bottom: 10px; }}
                    .value {{ font-weight: bold; color: #4a5568; }}
                    .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th, td {{ border: 1px solid #e2e8f0; padding: 12px; text-align: left; }}
                    th {{ background-color: #f7fafc; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>ED Capital - Piyasalara Genel Bakış (Tear Sheet)</h1>

                    <h2>Portföy Performans Özeti</h2>
                    <div class="metric">Net Kâr/Zarar (PnL): <span class="value">${total_pnl:.2f}</span></div>
                    <div class="metric">İsabet Oranı (Win Rate): <span class="value">{win_rate:.2f}%</span></div>
                    <div class="metric">Kâr Faktörü (Profit Factor): <span class="value">{profit_factor:.2f}</span></div>
                    <div class="metric">Maksimum Düşüş (Max Drawdown): <span class="value">{max_drawdown:.2f}%</span></div>

                    <h2>Risk & İstatistik Analizi</h2>
                    <div class="metric">Ortalama Kâr (Avg Win): <span class="value">${avg_win:.2f}</span></div>
                    <div class="metric">Ortalama Zarar (Avg Loss): <span class="value">${avg_loss:.2f}</span></div>
                    <div class="metric">Monte Carlo İflas Riski (Risk of Ruin): <span class="value">{risk_of_ruin}</span></div>
                    <div class="metric">Benchmark (USD/TRY B&H): <span class="value">{benchmark_return}</span></div>

                    <p><em>Not: Bu rapor otomatik olarak ED Capital Quant Engine tarafından oluşturulmuştur.</em></p>
                </div>
            </body>
            </html>
            """

            with open(filename, 'w') as f:
                f.write(html)

            logger.info(f"Tear Sheet generated: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error generating Tear Sheet: {e}")
            return None
