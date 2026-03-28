import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import pdfkit

# Phase 13 & 22: Reporting and Monte Carlo Simulation
class ReportEngine:
    def __init__(self, db_ref):
        self.db = db_ref
        os.makedirs("data/reports", exist_ok=True)

    def monte_carlo_risk_of_ruin(self, trades_df: pd.DataFrame, num_simulations=10000) -> tuple:
        if trades_df.empty or len(trades_df) < 5: return 0.0, 0.0

        pnl_array = trades_df['pnl'].fillna(0).values
        ruin_count = 0
        max_drawdowns = []

        simulations = np.random.choice(pnl_array, size=(num_simulations, len(pnl_array)), replace=True)
        cumulative_paths = np.cumsum(simulations, axis=1)

        for path in cumulative_paths:
            peak = np.maximum.accumulate(path)
            drawdown = (peak - path) / (10000 + peak)
            max_drawdowns.append(np.max(drawdown))
            if np.min(path) < -5000:
                ruin_count += 1

        risk_of_ruin = (ruin_count / num_simulations) * 100
        expected_mdd_99 = np.percentile(max_drawdowns, 99) * 100

        return risk_of_ruin, expected_mdd_99

    def generate_html_tear_sheet(self):
        trades = pd.read_sql_query("SELECT * FROM trades WHERE status='Closed'", self.db.conn)
        if trades.empty: return None

        total_pnl = trades['pnl'].sum()
        win_rate = len(trades[trades['pnl'] > 0]) / len(trades) * 100 if len(trades) > 0 else 0

        risk_of_ruin, mdd99 = self.monte_carlo_risk_of_ruin(trades)

        plt.figure(figsize=(10, 4))
        plt.plot(trades['pnl'].cumsum(), color='#1a365d', linewidth=2)
        plt.title('Kümülatif Getiri Eğrisi', fontsize=12, fontweight='bold')
        plt.grid(alpha=0.3)
        plt_path = "data/reports/equity_curve.png"
        plt.savefig(plt_path, bbox_inches='tight')
        plt.close()

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica', sans-serif; color: #333; }}
                .header {{ background-color: #1a365d; color: white; padding: 20px; text-align: center; }}
                h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 20px; }}
                .metrics {{ display: flex; justify-content: space-between; margin-bottom: 20px; }}
                .card {{ background: #f8fafc; padding: 15px; border-radius: 5px; width: 30%; border: 1px solid #e2e8f0; }}
                h2 {{ color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>ED CAPITAL - PİYASALARA GENEL BAKIŞ</h1>
                <p>Otonom Sistem Performans Özeti</p>
            </div>
            <div class="content">
                <h2>Temel Metrikler</h2>
                <div class="metrics">
                    <div class="card"><strong>Net PnL:</strong> <br><span style="color: {'green' if total_pnl>0 else 'red'}; font-size: 20px;">${total_pnl:.2f}</span></div>
                    <div class="card"><strong>İsabet Oranı:</strong> <br><span style="font-size: 20px;">{win_rate:.1f}%</span></div>
                    <div class="card"><strong>Risk of Ruin:</strong> <br><span style="font-size: 20px;">{risk_of_ruin:.2f}%</span></div>
                </div>
                <h2>Risk Analizi</h2>
                <p><strong>%99 Güven Aralığında Max Drawdown:</strong> {mdd99:.2f}%</p>
            </div>
        </body>
        </html>
        """

        html_path = "data/reports/tear_sheet.html"
        with open(html_path, "w") as f:
            f.write(html_content)

        return html_path
