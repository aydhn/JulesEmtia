import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any
import os

from .infrastructure import logger, PaperDB
from .config import INITIAL_CAPITAL

# ----------------- MONTE CARLO SIMULATION (Phase 22) -----------------
class MonteCarloSimulator:
    def __init__(self, db: PaperDB, num_simulations=10000):
        self.db = db
        self.num_simulations = num_simulations

    def run_simulation(self) -> Dict[str, Any]:
        """Fast Vectorized Monte Carlo Simulation."""
        closed_trades = self.db.get_closed_trades()
        if len(closed_trades) < 20:
            logger.warning("Not enough closed trades for Monte Carlo.")
            return {"risk_of_ruin": 0.0, "max_dd_99": 0.0}

        # Extract PnL Percentages (assuming initial capital for simplification in base metric)
        pnl_pcts = closed_trades['pnl'] / INITIAL_CAPITAL

        # Vectorized Numpy sampling with replacement
        simulated_returns = np.random.choice(pnl_pcts, size=(self.num_simulations, len(pnl_pcts)), replace=True)

        # Cumulative returns across 10,000 parallel paths
        cumulative_paths = np.cumprod(1 + simulated_returns, axis=1)

        # Calculate Drawdowns
        running_max = np.maximum.accumulate(cumulative_paths, axis=1)
        drawdowns = (running_max - cumulative_paths) / running_max
        max_drawdowns = np.max(drawdowns, axis=1)

        # 99% CI Max Drawdown
        max_dd_99 = np.percentile(max_drawdowns, 99)

        # Risk of Ruin (probability of losing 50% capital)
        ruin_paths = np.any(cumulative_paths < 0.5, axis=1)
        risk_of_ruin = np.mean(ruin_paths) * 100

        logger.info(f"Monte Carlo: 99% Max DD = {max_dd_99:.2%}, Risk of Ruin = {risk_of_ruin:.2f}%")

        return {
            "max_dd_99": max_dd_99,
            "risk_of_ruin": risk_of_ruin,
            "paths": cumulative_paths # for plotting
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
        profit_factor = closed_trades[closed_trades['pnl'] > 0]['pnl'].sum() / abs(closed_trades[closed_trades['pnl'] < 0]['pnl'].sum()) if closed_trades['pnl'].sum() != 0 else 0
        current_balance = INITIAL_CAPITAL + total_pnl

        # Monte Carlo Risk
        mc = MonteCarloSimulator(self.db)
        risk_metrics = mc.run_simulation()

        # Matplotlib Equity Curve
        plt.figure(figsize=(10, 5))
        closed_trades['cumulative_pnl'] = closed_trades['pnl'].cumsum() + INITIAL_CAPITAL
        plt.plot(closed_trades['exit_time'], closed_trades['cumulative_pnl'], color='darkblue', linewidth=2)
        plt.title('ED Capital - Kasa Büyüme Eğrisi', fontsize=14, fontweight='bold')
        plt.ylabel('Bakiye (USD)')
        plt.grid(alpha=0.3)
        plt.tight_layout()

        img_path = os.path.join(self.output_dir, "equity_curve.png")
        plt.savefig(img_path)
        plt.close()

        # HTML Generation (Phase 13 Strict Standard: No "Yonetici Ozeti")
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; margin: 40px; }}
                h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
                h2 {{ color: #2d3748; margin-top: 30px; }}
                .metric-box {{ background: #f7fafc; border-left: 4px solid #3182ce; padding: 15px; margin: 10px 0; }}
                .metric-title {{ font-weight: bold; color: #4a5568; }}
                .metric-value {{ font-size: 1.2em; color: #2b6cb0; }}
            </style>
        </head>
        <body>
            <h1>Piyasalara Genel Bakış (ED Capital Quant Engine)</h1>

            <div class="metric-box">
                <span class="metric-title">Başlangıç Bakiyesi:</span> <span class="metric-value">${INITIAL_CAPITAL:,.2f}</span><br>
                <span class="metric-title">Güncel Bakiye:</span> <span class="metric-value">${current_balance:,.2f}</span><br>
                <span class="metric-title">Net PnL:</span> <span class="metric-value">${total_pnl:,.2f}</span>
            </div>

            <div class="metric-box">
                <span class="metric-title">İsabet Oranı (Win Rate):</span> <span class="metric-value">{win_rate:.1f}%</span><br>
                <span class="metric-title">Kâr Faktörü (Profit Factor):</span> <span class="metric-value">{profit_factor:.2f}</span><br>
                <span class="metric-title">%99 Güven Aralığı Max Drawdown:</span> <span class="metric-value">{risk_metrics['max_dd_99']:.2%}</span><br>
                <span class="metric-title">İflas Riski (Risk of Ruin):</span> <span class="metric-value">{risk_metrics['risk_of_ruin']:.2f}%</span>
            </div>

            <h2>Kasa Büyüme Eğrisi</h2>
            <img src="equity_curve.png" alt="Equity Curve" style="max-width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 5px;">

        </body>
        </html>
        """

        html_path = os.path.join(self.output_dir, "tear_sheet.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet generated at {html_path}")
        return html_path
