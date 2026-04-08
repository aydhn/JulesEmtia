import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, Any
import os

from .infrastructure import logger, PaperDB
from .config import INITIAL_CAPITAL

# ----------------- MONTE CARLO SIMULATION (Phase 22) -----------------
class MonteCarloSimulator:
    def __init__(self, db: PaperDB, num_simulations=10000):
        self.db = db
        self.num_simulations = num_simulations
        self.output_dir = "reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def run_simulation(self) -> Dict[str, Any]:
        """Fast Vectorized Monte Carlo Simulation with Plotting."""
        closed_trades = self.db.get_closed_trades()
        if len(closed_trades) < 20:
            logger.warning("Not enough closed trades for Monte Carlo.")
            return {"risk_of_ruin": 0.0, "max_dd_99": 0.0}

        pnl_pcts = closed_trades['pnl'] / INITIAL_CAPITAL

        simulated_returns = np.random.choice(pnl_pcts, size=(self.num_simulations, len(pnl_pcts)), replace=True)
        cumulative_paths = np.cumprod(1 + simulated_returns, axis=1)

        running_max = np.maximum.accumulate(cumulative_paths, axis=1)
        drawdowns = (running_max - cumulative_paths) / running_max
        max_drawdowns = np.max(drawdowns, axis=1)

        max_dd_99 = np.percentile(max_drawdowns, 99)
        ruin_paths = np.any(cumulative_paths < 0.5, axis=1)
        risk_of_ruin = np.mean(ruin_paths) * 100

        logger.info(f"Monte Carlo: 99% Max DD = {max_dd_99:.2%}, Risk of Ruin = {risk_of_ruin:.2f}%")

        # Plotting Spaghetti Plot
        plt.figure(figsize=(10, 5))
        for i in range(min(100, self.num_simulations)):
            plt.plot(cumulative_paths[i] * INITIAL_CAPITAL, color='grey', alpha=0.1)
        plt.title('Monte Carlo Spaghetti Plot (100 Simulations)', fontsize=14, fontweight='bold')
        plt.ylabel('Bakiye (USD)')
        plt.xlabel('İşlem Sayısı')
        plt.grid(alpha=0.3)
        plt.tight_layout()

        mc_path = os.path.join(self.output_dir, "monte_carlo.png")
        plt.savefig(mc_path)
        plt.close()

        return {
            "max_dd_99": max_dd_99,
            "risk_of_ruin": risk_of_ruin,
        }

# ----------------- ED CAPITAL TEAR SHEET (Phase 13) -----------------
class Reporter:
    def __init__(self, db: PaperDB):
        self.db = db
        self.output_dir = "reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_tear_sheet(self) -> str:
        """Generates ED Capital Kurumsal Sablonu HTML Report."""
        logger.info("Generating Tear Sheet...")
        closed_trades = self.db.get_closed_trades()

        if closed_trades.empty:
            return "No closed trades yet to report."

        # Basic Metrics
        total_pnl = closed_trades['pnl'].sum()
        win_rate = (closed_trades['pnl'] > 0).mean() * 100

        wins = closed_trades[closed_trades['pnl'] > 0]
        losses = closed_trades[closed_trades['pnl'] < 0]

        profit_factor = wins['pnl'].sum() / abs(losses['pnl'].sum()) if not losses.empty and losses['pnl'].sum() != 0 else float('inf')

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        current_balance = INITIAL_CAPITAL + total_pnl

        # Monte Carlo Risk
        mc = MonteCarloSimulator(self.db)
        risk_metrics = mc.run_simulation()

        # Matplotlib Equity Curve
        plt.figure(figsize=(10, 5))
        closed_trades['cumulative_pnl'] = closed_trades['pnl'].cumsum() + INITIAL_CAPITAL
        # Using string conversion for categorical plotting or just plot by index if dates are not perfectly parsed
        plt.plot(closed_trades.index, closed_trades['cumulative_pnl'], color='darkblue', linewidth=2)
        plt.title('ED Capital - Kasa Büyüme Eğrisi', fontsize=14, fontweight='bold')
        plt.ylabel('Bakiye (USD)')
        plt.xlabel('İşlem Sayısı')
        plt.grid(alpha=0.3)
        plt.tight_layout()

        img_path = os.path.join(self.output_dir, "equity_curve.png")
        plt.savefig(img_path)
        plt.close()

        # HTML Generation (Phase 13 Strict Standard)
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; margin: 40px; background-color: #f8f9fa; }}
                .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
                h2 {{ color: #2d3748; margin-top: 30px; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; }}
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
                .metric-box {{ background: #ebf8ff; border-left: 4px solid #3182ce; padding: 15px; border-radius: 4px; }}
                .metric-title {{ font-weight: bold; color: #2c5282; display: block; margin-bottom: 5px; }}
                .metric-value {{ font-size: 1.4em; color: #1a365d; font-weight: bold; }}
                .img-container {{ text-align: center; margin-top: 20px; }}
                img {{ max-width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 10px; border: 1px solid #e2e8f0; text-align: left; }}
                th {{ background-color: #edf2f7; color: #2d3748; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Piyasalara Genel Bakış (ED Capital Quant Engine)</h1>

                <div class="grid">
                    <div class="metric-box">
                        <span class="metric-title">Başlangıç Bakiyesi</span>
                        <span class="metric-value">${INITIAL_CAPITAL:,.2f}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-title">Güncel Bakiye</span>
                        <span class="metric-value">${current_balance:,.2f}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-title">Toplam Net Kâr/Zarar</span>
                        <span class="metric-value" style="color: {'#38a169' if total_pnl >= 0 else '#e53e3e'};">${total_pnl:,.2f}</span>
                    </div>
                    <div class="metric-box">
                        <span class="metric-title">Toplam İşlem Sayısı</span>
                        <span class="metric-value">{len(closed_trades)}</span>
                    </div>
                </div>

                <h2>Performans Metrikleri</h2>
                <table>
                    <tr>
                        <th>Metrik</th>
                        <th>Değer</th>
                    </tr>
                    <tr>
                        <td>İsabet Oranı (Win Rate)</td>
                        <td>{win_rate:.1f}%</td>
                    </tr>
                    <tr>
                        <td>Kâr Faktörü (Profit Factor)</td>
                        <td>{profit_factor:.2f}</td>
                    </tr>
                    <tr>
                        <td>Ortalama Kâr (Average Win)</td>
                        <td><span style="color: #38a169;">${avg_win:,.2f}</span></td>
                    </tr>
                    <tr>
                        <td>Ortalama Zarar (Average Loss)</td>
                        <td><span style="color: #e53e3e;">${avg_loss:,.2f}</span></td>
                    </tr>
                </table>

                <h2>Risk Metrikleri (Monte Carlo)</h2>
                <table>
                    <tr>
                        <th>Metrik</th>
                        <th>Değer</th>
                    </tr>
                    <tr>
                        <td>%99 Güven Aralığı Beklenen Max Drawdown</td>
                        <td>{risk_metrics['max_dd_99']:.2%}</td>
                    </tr>
                    <tr>
                        <td>İflas Riski (Risk of Ruin - %50 Kayıp)</td>
                        <td>{risk_metrics['risk_of_ruin']:.2f}%</td>
                    </tr>
                </table>

                <h2>Kasa Büyüme Eğrisi</h2>
                <div class="img-container">
                    <img src="equity_curve.png" alt="Equity Curve">
                </div>

                <h2>Monte Carlo Simülasyonu (Stres Testi)</h2>
                <div class="img-container">
                    <img src="monte_carlo.png" alt="Monte Carlo Spagetti Grafiği">
                </div>
            </div>
        </body>
        </html>
        """

        html_path = os.path.join(self.output_dir, "tear_sheet.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet generated at {html_path}")
        return html_path
