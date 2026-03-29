import pandas as pd
import matplotlib.pyplot as plt
import os
from analysis.monte_carlo import MonteCarloSimulator

class ReportEngine:
    def __init__(self, db_ref):
        self.db = db_ref
        os.makedirs("data/reports", exist_ok=True)
        self.mc_sim = MonteCarloSimulator()

    def generate_html_tear_sheet(self):
        trades = pd.read_sql_query("SELECT * FROM trades WHERE status='Closed'", self.db.conn)
        if trades.empty: return None

        total_pnl = trades['pnl'].sum()
        win_rate = len(trades[trades['pnl'] > 0]) / len(trades) * 100 if len(trades) > 0 else 0

        risk_of_ruin, mdd99 = self.mc_sim.risk_of_ruin(trades)

        # Matplotlib visualization without GUI
        plt.figure(figsize=(10, 4))
        plt.plot(trades['pnl'].cumsum(), color='#1a365d', linewidth=2)
        plt.title('Kümülatif Getiri Eğrisi', fontsize=12, fontweight='bold')
        plt.grid(alpha=0.3)
        plt_path = "data/reports/equity_curve.png"
        plt.savefig(plt_path, bbox_inches='tight')
        plt.close()

        # ED Capital Corporate Template
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
                    <div class="card"><strong>İflas Riski (Risk of Ruin):</strong> <br><span style="font-size: 20px;">{risk_of_ruin:.2f}%</span></div>
                </div>
                <h2>Risk Analizi</h2>
                <p><strong>%99 Güven Aralığında Max Drawdown:</strong> {mdd99:.2f}%</p>
                <img src="equity_curve.png" style="width:100%; margin-top: 20px;" />
            </div>
        </body>
        </html>
        """

        html_path = "data/reports/tear_sheet.html"
        with open(html_path, "w") as f:
            f.write(html_content)

        return html_path
