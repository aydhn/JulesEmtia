import pandas as pd
import os
import matplotlib.pyplot as plt
from jinja2 import Template
import datetime
from .logger import quant_logger
from .config import REPORTS_DIR

class Reporter:
    @staticmethod
    def generate_html_tearsheet(closed_trades: pd.DataFrame, balance: float, mc_results: dict):
        """Phase 13: ED Capital Kurumsal Şablonu Tear Sheet"""
        try:
            report_path = os.path.join(REPORTS_DIR, f"ED_Capital_Tearsheet_{datetime.datetime.now().strftime('%Y%m%d')}.html")

            # Metrics calculation
            total_pnl = closed_trades['net_pnl'].sum() if not closed_trades.empty else 0.0
            wins = closed_trades[closed_trades['net_pnl'] > 0]
            losses = closed_trades[closed_trades['net_pnl'] <= 0]
            win_rate = (len(wins) / len(closed_trades)) * 100 if not closed_trades.empty else 0.0
            profit_factor = abs(wins['net_pnl'].sum() / losses['net_pnl'].sum()) if not losses.empty and losses['net_pnl'].sum() != 0 else 0.0

            # Plot Equity Curve
            if not closed_trades.empty:
                closed_trades['cum_pnl'] = closed_trades['net_pnl'].cumsum()
                plt.figure(figsize=(10,4))
                plt.plot(closed_trades['cum_pnl'].values, color='#0a3d62', linewidth=2)
                plt.title("Kümülatif Getiri (Net PnL)")
                plt.grid(alpha=0.3)
                plot_path = os.path.join(REPORTS_DIR, "equity_curve.png")
                plt.savefig(plot_path)
                plt.close()

            # HTML Template - STRICT ED CAPITAL CORPORATE FORMAT
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { font-family: 'Arial', sans-serif; color: #333; margin: 40px; }
                    .header { background-color: #0a3d62; color: white; padding: 20px; text-align: center; }
                    h1 { margin: 0; font-size: 24px; letter-spacing: 2px; }
                    h2 { color: #0a3d62; border-bottom: 2px solid #0a3d62; padding-bottom: 5px; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { padding: 12px; border: 1px solid #ddd; text-align: left; }
                    th { background-color: #f5f6fa; }
                    .positive { color: #27ae60; font-weight: bold; }
                    .negative { color: #e74c3c; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>ED CAPITAL QUANT ENGINE</h1>
                    <p>Kurumsal Performans Raporu | {{ date }}</p>
                </div>

                <h2>Piyasalara Genel Bakış</h2>
                <table>
                    <tr><th>Güncel Bakiye</th><td>${{ balance }}</td></tr>
                    <tr><th>Net PnL</th><td class="{{ 'positive' if pnl > 0 else 'negative' }}">${{ pnl }}</td></tr>
                    <tr><th>İsabet Oranı (Win Rate)</th><td>%{{ win_rate }}</td></tr>
                    <tr><th>Kâr Faktörü (Profit Factor)</th><td>{{ profit_factor }}</td></tr>
                </table>

                <h2>Stres Testi ve Monte Carlo Simülasyonu</h2>
                <table>
                    <tr><th>%99 Güven Aralığında Max Drawdown</th><td class="negative">%{{ mc_dd }}</td></tr>
                    <tr><th>İflas Riski (Risk of Ruin)</th><td>%{{ mc_ruin }}</td></tr>
                </table>

                <h2>Kasa Büyüme Eğrisi</h2>
                <img src="equity_curve.png" width="100%" alt="Equity Curve">
            </body>
            </html>
            """

            template = Template(html_template)
            rendered = template.render(
                date=datetime.datetime.now().strftime('%Y-%m-%d'),
                balance=f"{balance:,.2f}",
                pnl=f"{total_pnl:,.2f}",
                win_rate=f"{win_rate:.2f}",
                profit_factor=f"{profit_factor:.2f}",
                mc_dd=f"{mc_results.get('max_dd_99', 0.0):.2f}",
                mc_ruin=f"{mc_results.get('risk_of_ruin', 0.0):.2f}"
            )

            with open(report_path, "w", encoding='utf-8') as f:
                f.write(rendered)

            quant_logger.info(f"Tear sheet generated at {report_path}")
            return report_path
        except Exception as e:
            quant_logger.error(f"Tearsheet generation failed: {e}")
            return None
