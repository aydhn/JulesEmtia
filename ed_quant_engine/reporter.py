import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import datetime
from logger import get_logger
import paper_db

logger = get_logger("reporter")

class ReportGenerator:
    """Generates ED Capital Corporate Standard Performance Reports."""

    def __init__(self):
        os.makedirs("reports", exist_ok=True)
        # Corporate Styling
        plt.style.use('dark_background')
        sns.set_palette("muted")

    def _calculate_metrics(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {}

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        total_pnl = df['pnl'].sum()
        win_rate = len(wins) / len(df) if len(df) > 0 else 0

        gross_profit = wins['pnl'].sum()
        gross_loss = abs(losses['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        # Max Drawdown Calculation
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['peak'] = df['cumulative_pnl'].cummax()
        df['drawdown'] = df['cumulative_pnl'] - df['peak']
        max_drawdown = df['drawdown'].min()

        return {
            "Total PnL": total_pnl,
            "Win Rate": win_rate,
            "Profit Factor": profit_factor,
            "Max Drawdown": max_drawdown,
            "Avg Win": avg_win,
            "Avg Loss": avg_loss,
            "Total Trades": len(df)
        }

    def run_monte_carlo(self, df: pd.DataFrame, simulations: int = 10000) -> dict:
        """Runs Fast Numpy Vectorized Monte Carlo Stress Test."""
        if len(df) < 10:
            return {"99% Expected Drawdown": 0, "Risk of Ruin": 0}

        returns = df['pnl'].values
        n_trades = len(returns)

        # Vectorized resampling: Matrix of shape (simulations, n_trades)
        simulated_paths = np.random.choice(returns, size=(simulations, n_trades), replace=True)

        # Cumulative PnL paths
        cumulative_paths = np.cumsum(simulated_paths, axis=1)

        # Max Drawdowns for each path
        peaks = np.maximum.accumulate(cumulative_paths, axis=1)
        drawdowns = cumulative_paths - peaks
        max_drawdowns = np.min(drawdowns, axis=1) # Negative values

        # 99% Confidence Interval Expected Drawdown (Percentile 1% because it's negative)
        expected_drawdown_99 = np.percentile(max_drawdowns, 1)

        # Risk of Ruin: Probability of losing 50% of starting capital (assuming 10k start)
        ruin_threshold = -5000.0
        ruin_count = np.sum(np.any(cumulative_paths <= ruin_threshold, axis=1))
        risk_of_ruin = (ruin_count / simulations) * 100

        logger.info(f"Monte Carlo: 99% Drawdown = ${expected_drawdown_99:.2f}, Risk of Ruin = {risk_of_ruin:.2f}%")

        return {
            "99% Expected Drawdown": expected_drawdown_99,
            "Risk of Ruin": risk_of_ruin
        }

    def generate_html_report(self):
        """Generates a standalone HTML Tear Sheet."""
        raw_trades = paper_db.get_closed_trades()
        if not raw_trades:
            logger.warning("No closed trades to report.")
            return None

        df = pd.DataFrame(raw_trades)
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df = df.sort_values('exit_time')

        metrics = self._calculate_metrics(df)
        mc_risk = self.run_monte_carlo(df)

        # --- Generate Equity Curve ---
        plt.figure(figsize=(10, 4))
        plt.plot(df['exit_time'], df['cumulative_pnl'], color='cyan', linewidth=2)
        plt.fill_between(df['exit_time'], df['cumulative_pnl'], color='cyan', alpha=0.1)
        plt.title('ED Capital - Kümülatif Getiri (Equity Curve)', color='white')
        plt.xlabel('Tarih', color='gray')
        plt.ylabel('PnL ($)', color='gray')
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        chart_path = "reports/equity_curve.png"
        plt.savefig(chart_path, facecolor='#1e1e1e')
        plt.close()

        # HTML Template Generation
        html_content = f"""
        <html>
        <head>
            <title>ED Capital Quant Engine - Performans Raporu</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 40px; }}
                h1 {{ color: #00d2ff; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                h2 {{ color: #aaaaaa; }}
                .metric-container {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 30px; }}
                .metric-box {{ background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 20px; width: 200px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #fff; margin-top: 10px; }}
                .positive {{ color: #4caf50; }}
                .negative {{ color: #f44336; }}
                .chart {{ margin-top: 30px; border: 1px solid #333; border-radius: 8px; padding: 10px; background-color: #1e1e1e; }}
            </style>
        </head>
        <body>
            <h1>Piyasalara Genel Bakış (ED Capital Quant Engine)</h1>
            <p>Tarih: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

            <h2>Performans Metrikleri</h2>
            <div class="metric-container">
                <div class="metric-box">
                    <div>Net PnL</div>
                    <div class="metric-value {'positive' if metrics.get('Total PnL', 0) > 0 else 'negative'}">
                        ${metrics.get('Total PnL', 0):.2f}
                    </div>
                </div>
                <div class="metric-box">
                    <div>İsabet Oranı (Win Rate)</div>
                    <div class="metric-value">
                        {metrics.get('Win Rate', 0)*100:.1f}%
                    </div>
                </div>
                <div class="metric-box">
                    <div>Kâr Faktörü (Profit Factor)</div>
                    <div class="metric-value">
                        {metrics.get('Profit Factor', 0):.2f}
                    </div>
                </div>
                <div class="metric-box">
                    <div>Gerçekleşen Max Düşüş</div>
                    <div class="metric-value negative">
                        ${metrics.get('Max Drawdown', 0):.2f}
                    </div>
                </div>
                <div class="metric-box">
                    <div>İşlem Sayısı</div>
                    <div class="metric-value">{metrics.get('Total Trades', 0)}</div>
                </div>
            </div>

            <h2>Stres Testi ve Risk (Monte Carlo 10K Simülasyon)</h2>
            <div class="metric-container">
                <div class="metric-box">
                    <div>%99 Beklenen Max Düşüş</div>
                    <div class="metric-value negative">
                        ${mc_risk.get('99% Expected Drawdown', 0):.2f}
                    </div>
                </div>
                <div class="metric-box">
                    <div>İflas Riski (Risk of Ruin)</div>
                    <div class="metric-value {'negative' if mc_risk.get('Risk of Ruin', 0) > 1 else 'positive'}">
                        {mc_risk.get('Risk of Ruin', 0):.2f}%
                    </div>
                </div>
            </div>

            <div class="chart">
                <h2>Kasa Büyüme Eğrisi</h2>
                <img src="equity_curve.png" alt="Equity Curve" style="width: 100%; max-width: 800px;">
            </div>
        </body>
        </html>
        """

        report_path = f"reports/TearSheet_{datetime.datetime.now().strftime('%Y%m%d')}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet generated: {report_path}")
        return report_path

if __name__ == "__main__":
    rep = ReportGenerator()
    rep.generate_html_report()
