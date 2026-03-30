import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from system.logger import log
from core.data_engine import db

class Analyzer:
    @staticmethod
    def run_monte_carlo(simulations=10000):
        """Phase 22: Monte Carlo Risk of Ruin Simulation"""
        try:
            trades = pd.read_sql_query("SELECT pnl FROM trades WHERE status='CLOSED'", db.conn)
            if len(trades) < 10:
                log.info("Not enough trades for Monte Carlo.")
                return None

            pnls = trades['pnl'].values
            results = []

            plt.figure(figsize=(10, 6))

            for i in range(simulations):
                sim_pnls = np.random.choice(pnls, size=len(pnls), replace=True)
                cumulative = np.cumsum(sim_pnls)
                max_dd = np.min(cumulative) if np.min(cumulative) < 0 else 0
                results.append(max_dd)

                # Plot subset of simulations for Spaghetti Plot
                if i < 100:
                    plt.plot(cumulative, color='grey', alpha=0.1)

            expected_dd_99 = np.percentile(results, 1) # 1st percentile of worst drops
            risk_of_ruin = np.sum(np.array(results) < -5000) / simulations # Assuming 50% loss of $10k

            plt.title("Monte Carlo Spaghetti Plot (100 Simulations)")
            plt.xlabel("Trade Number")
            plt.ylabel("Cumulative PnL")
            plt.savefig("monte_carlo.png")
            plt.close()

            log.info(f"Monte Carlo 99% CI Expected Max DD: ${abs(expected_dd_99):.2f}")
            log.info(f"Risk of Ruin (>50% loss): {risk_of_ruin*100:.2f}%")

            return {"exp_dd_99": expected_dd_99, "risk_of_ruin": risk_of_ruin}
        except Exception as e:
            log.error(f"Monte Carlo Error: {e}")
            return None

    @staticmethod
    def generate_tear_sheet():
        """Phase 13: ED Capital Kurumsal Şablonlu HTML Rapor"""
        try:
            trades = pd.read_sql_query("SELECT * FROM trades WHERE status='CLOSED'", db.conn)
            if trades.empty:
                return "Piyasalara Genel Bakış\n\nHenüz kapalı işlem bulunmamaktadır."

            total_pnl = trades['pnl'].sum()
            wins = trades[trades['pnl'] > 0]
            losses = trades[trades['pnl'] <= 0]

            win_rate = len(wins) / len(trades) if len(trades) > 0 else 0
            profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else float('inf')

            mc_stats = Analyzer.run_monte_carlo(1000)

            # Equity Curve
            trades['cumulative_pnl'] = trades['pnl'].cumsum()
            plt.figure(figsize=(10, 6))
            plt.plot(trades['cumulative_pnl'], color='blue', linewidth=2)
            plt.title('Equity Curve (Kasa Büyüme Eğrisi)')
            plt.xlabel('Trades')
            plt.ylabel('Cumulative PnL')
            plt.grid(True)
            plt.savefig('equity_curve.png')
            plt.close()

            html_content = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
                    h1 {{ color: #004080; }}
                    .summary {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
                    img {{ max-width: 100%; height: auto; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <h1>Piyasalara Genel Bakış</h1>
                <div class="summary">
                    <p><strong>Toplam İşlem:</strong> {len(trades)}</p>
                    <p><strong>Net PnL:</strong> ${total_pnl:.2f}</p>
                    <p><strong>Win Rate:</strong> {win_rate*100:.1f}%</p>
                    <p><strong>Profit Factor:</strong> {profit_factor:.2f}</p>
            """
            if mc_stats:
                html_content += f"""
                    <p><strong>99% CI Max DD:</strong> ${abs(mc_stats['exp_dd_99']):.2f}</p>
                    <p><strong>Risk of Ruin:</strong> {mc_stats['risk_of_ruin']*100:.2f}%</p>
                """
            html_content += """
                </div>
                <h2>Equity Curve</h2>
                <img src="equity_curve.png" alt="Equity Curve">
                <h2>Monte Carlo Simulation</h2>
                <img src="monte_carlo.png" alt="Monte Carlo">
            </body>
            </html>
            """

            with open("tear_sheet.html", "w", encoding="utf-8") as f:
                f.write(html_content)

            return "HTML rapor 'tear_sheet.html' olarak oluşturuldu."
        except Exception as e:
            log.error(f"Report Generation Error: {e}")
            return "Rapor oluşturulamadı."
