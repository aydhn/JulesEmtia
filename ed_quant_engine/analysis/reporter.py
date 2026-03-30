import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from core.paper_db import PaperDB
from core.logger import get_logger

logger = get_logger()

class ReportEngine:
    def __init__(self, db: PaperDB):
        self.db = db

    def generate_tear_sheet(self) -> str:
        """Generates ED Capital Institutional Tear Sheet (HTML/PDF output)."""
        logger.info("ED Capital Tear Sheet Hazırlanıyor...")

        trades = self.db.fetch_all("SELECT ticker, direction, entry_price, exit_price, pnl, cost FROM trades WHERE status = 'Closed'")

        if not trades:
            return "Henüz kapalı işlem bulunmamaktadır."

        df = pd.DataFrame(trades, columns=['Ticker', 'Direction', 'Entry', 'Exit', 'PnL', 'Cost'])

        # Core Metrics
        total_pnl = df['PnL'].sum()
        win_rate = len(df[df['PnL'] > 0]) / len(df) * 100 if len(df) > 0 else 0

        gross_profit = df[df['PnL'] > 0]['PnL'].sum()
        gross_loss = abs(df[df['PnL'] < 0]['PnL'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_win = df[df['PnL'] > 0]['PnL'].mean() if gross_profit > 0 else 0
        avg_loss = df[df['PnL'] < 0]['PnL'].mean() if gross_loss > 0 else 0

        # Equity Curve
        df['Cumulative_PnL'] = df['PnL'].cumsum()
        max_drawdown = self._calculate_max_drawdown(df['Cumulative_PnL'])

        # Monte Carlo Risk of Ruin
        ruin_prob, mc_drawdown = self._run_monte_carlo(df['PnL'].values)

        # Generate HTML Report (ED Capital Template)
        html_report = f"""
        <html>
        <head>
            <title>ED Capital Quant Engine - Performans Raporu</title>
            <style>
                body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; margin: 40px; }}
                h1 {{ color: #0a2540; border-bottom: 2px solid #0a2540; padding-bottom: 10px; }}
                h2 {{ color: #1a457b; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #f4f7f6; color: #0a2540; }}
                .positive {{ color: #28a745; font-weight: bold; }}
                .negative {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Piyasalara Genel Bakış ve Performans Özeti</h1>
            <p><strong>Rapor Tarihi:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>

            <h2>Sistem İstatistikleri</h2>
            <table>
                <tr><th>Metrik</th><th>Değer</th></tr>
                <tr><td>Toplam Net Kâr/Zarar</td><td class="{'positive' if total_pnl > 0 else 'negative'}">${total_pnl:.2f}</td></tr>
                <tr><td>Win Rate (İsabet Oranı)</td><td>%{win_rate:.1f}</td></tr>
                <tr><td>Profit Factor (Kâr Faktörü)</td><td>{profit_factor:.2f}</td></tr>
                <tr><td>Ortalama Kâr / Ortalama Zarar</td><td>${avg_win:.2f} / ${avg_loss:.2f}</td></tr>
                <tr><td>Max Drawdown (Maksimum Düşüş)</td><td class="negative">%{max_drawdown:.2f}</td></tr>
            </table>

            <h2>Monte Carlo Stres Testi (10.000 Simülasyon)</h2>
            <table>
                <tr><th>Metrik</th><th>Değer</th></tr>
                <tr><td>İflas Riski (Risk of Ruin)</td><td>%{ruin_prob:.2f}</td></tr>
                <tr><td>%99 Güven Aralığında Beklenen Max Drawdown</td><td>%{mc_drawdown:.2f}</td></tr>
            </table>

            <p style="margin-top:50px; font-size: 12px; color: #777;">ED Capital - Tescilli Gizli Doküman. Dışarıya paylaşılamaz.</p>
        </body>
        </html>
        """

        # Save to disk
        report_path = "ed_capital_tear_sheet.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_report)

        # Plot Equity Curve
        plt.figure(figsize=(10,5))
        plt.plot(df['Cumulative_PnL'], label='Cumulative PnL', color='#0a2540', linewidth=2)
        plt.title('ED Capital - Kasa Büyüme Eğrisi')
        plt.xlabel('Trade #')
        plt.ylabel('Net PnL ($)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.savefig('equity_curve.png')
        plt.close()

        logger.info(f"Rapor oluşturuldu: {report_path}")
        return report_path

    def _calculate_max_drawdown(self, cumulative_pnl: pd.Series) -> float:
        rolling_max = cumulative_pnl.expanding().max()
        drawdown = (cumulative_pnl - rolling_max) / rolling_max.replace(0, 1) # Prevent div by 0
        return abs(drawdown.min() * 100) if not drawdown.empty else 0.0

    def _run_monte_carlo(self, pnl_array: np.ndarray, simulations=10000) -> tuple:
        """Runs 10,000 simulations using Vectorized Numpy array sampling."""
        if len(pnl_array) < 10: return 0.0, 0.0

        # Random choice with replacement (10k rows x N trades)
        simulated_paths = np.random.choice(pnl_array, size=(simulations, len(pnl_array)), replace=True)
        cumulative_paths = np.cumsum(simulated_paths, axis=1)

        # Drawdown calculation
        running_max = np.maximum.accumulate(cumulative_paths, axis=1)
        drawdowns = (cumulative_paths - running_max) / (running_max + 1e-9)
        max_drawdowns = np.min(drawdowns, axis=1)

        # Metrics
        ruin_probability = np.mean(np.min(cumulative_paths, axis=1) < -5000) * 100 # Ruin = Loss > $5k
        expected_drawdown_99 = abs(np.percentile(max_drawdowns, 1)) * 100

        return ruin_probability, expected_drawdown_99
