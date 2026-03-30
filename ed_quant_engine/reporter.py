import pandas as pd
import matplotlib.pyplot as plt
import os
import datetime
from jinja2 import Template
from paper_db import PaperDB
from monte_carlo import MonteCarloRisk
from logger import logger
from notifier import async_send_telegram_message

class TearSheetReporter:
    """
    Phase 13 & 22: Corporate Reporting & Performance Summary (Tear Sheet).
    Generates professional HTML/PDF reports following ED Capital standards.
    Integrates Monte Carlo Stress Testing metrics.
    """

    REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')
    os.makedirs(REPORTS_DIR, exist_ok=True)

    @classmethod
    def get_closed_trades_df(cls) -> pd.DataFrame:
        rows = PaperDB.fetch_all("SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time ASC")
        df = pd.DataFrame([dict(row) for row in rows])

        if not df.empty:
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df['net_pnl'] = pd.to_numeric(df['net_pnl'])

        return df

    @classmethod
    def calculate_metrics(cls, df: pd.DataFrame) -> dict:
        if df.empty:
            return {"Total PnL": 0.0, "Win Rate": "0.0%", "Profit Factor": "0.0", "Max Drawdown": "0.0%"}

        total_pnl = df['net_pnl'].sum()
        wins = df[df['net_pnl'] > 0]
        losses = df[df['net_pnl'] <= 0]

        win_rate = len(wins) / len(df) if len(df) > 0 else 0

        gross_profit = wins['net_pnl'].sum()
        gross_loss = abs(losses['net_pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

        start_bal = float(os.getenv("PAPER_STARTING_BALANCE", 10000.0))
        df['Equity'] = start_bal + df['net_pnl'].cumsum()

        df['Peak'] = df['Equity'].cummax()
        df['Drawdown'] = (df['Equity'] - df['Peak']) / df['Peak']
        max_dd = df['Drawdown'].min() * 100

        metrics = {
            "Total PnL": f"${total_pnl:.2f}",
            "Win Rate": f"{win_rate:.1%}",
            "Profit Factor": f"{profit_factor:.2f}",
            "Max Drawdown": f"{max_dd:.2f}%",
            "Avg Win": f"${wins['net_pnl'].mean():.2f}" if not wins.empty else "$0.0",
            "Avg Loss": f"${losses['net_pnl'].mean():.2f}" if not losses.empty else "$0.0"
        }

        # Phase 22: Integrate Monte Carlo Metrics
        mc_results = MonteCarloRisk.run_simulation(n_simulations=10000)
        metrics.update(mc_results)

        return metrics

    @classmethod
    def generate_equity_curve(cls, df: pd.DataFrame, filepath: str):
        if df.empty: return

        start_bal = float(os.getenv("PAPER_STARTING_BALANCE", 10000.0))
        df['Equity'] = start_bal + df['net_pnl'].cumsum()

        plt.figure(figsize=(10, 5))
        plt.plot(df['exit_time'], df['Equity'], color='#003366', linewidth=2)
        plt.fill_between(df['exit_time'], df['Equity'], start_bal, alpha=0.1, color='#003366')
        plt.axhline(y=start_bal, color='gray', linestyle='--', alpha=0.5)

        plt.title('ED Capital - Kümülatif Getiri Eğrisi', fontsize=14, fontweight='bold', color='#003366')
        plt.xlabel('Tarih')
        plt.ylabel('Portföy Değeri ($)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()

    @classmethod
    async def generate_report(cls) -> str:
        logger.info("Generating Weekly Tear Sheet with Monte Carlo Risk Metrics...")

        df = cls.get_closed_trades_df()
        metrics = cls.calculate_metrics(df)

        eq_curve_path = os.path.join(cls.REPORTS_DIR, 'equity_curve.png')
        cls.generate_equity_curve(df, eq_curve_path)

        html_template = """
        <html>
        <head>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 40px; background-color: #f4f6f9; }
                .container { max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                .header { border-bottom: 3px solid #003366; padding-bottom: 15px; margin-bottom: 30px; text-align: center; }
                h1 { color: #003366; margin: 0; font-size: 28px; text-transform: uppercase; letter-spacing: 1px; }
                .subtitle { color: #666; font-size: 16px; margin-top: 5px; }
                h2 { color: #003366; border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 40px; }
                .metrics-container { display: flex; flex-wrap: wrap; gap: 20px; justify-content: space-between; margin-bottom: 40px; }
                .metric-card { background: #fff; padding: 20px; border-radius: 8px; text-align: center; flex: 1 1 calc(33.333% - 20px); box-shadow: 0 2px 5px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }
                .metric-card h3 { margin: 0 0 10px 0; color: #555; font-size: 14px; text-transform: uppercase; }
                .metric-card h2 { margin: 0; color: #003366; font-size: 24px; border: none; padding: 0; }
                .risk-section .metric-card { background: #fff8f8; border-color: #ffcccc; }
                .risk-section .metric-card h2 { color: #cc0000; }
                .img-container { text-align: center; margin-top: 40px; }
                img { max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd; }
                .footer { text-align: center; font-size: 11px; color: #999; margin-top: 60px; border-top: 1px solid #eee; padding-top: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ED CAPITAL QUANT ENGINE</h1>
                    <div class="subtitle">Piyasalara Genel Bakış - Kantitatif Performans ve Risk Raporu</div>
                    <div class="subtitle" style="font-size: 14px;">Tarih: {{ date }}</div>
                </div>

                <h2>Temel Performans Metrikleri</h2>
                <div class="metrics-container">
                    <div class="metric-card"><h3>Toplam Net PnL</h3><h2>{{ metrics['Total PnL'] }}</h2></div>
                    <div class="metric-card"><h3>İsabet Oranı (Win Rate)</h3><h2>{{ metrics['Win Rate'] }}</h2></div>
                    <div class="metric-card"><h3>Kâr Faktörü (Profit Factor)</h3><h2>{{ metrics['Profit Factor'] }}</h2></div>
                    <div class="metric-card"><h3>Ortalama Kâr</h3><h2>{{ metrics['Avg Win'] }}</h2></div>
                    <div class="metric-card"><h3>Ortalama Zarar</h3><h2>{{ metrics['Avg Loss'] }}</h2></div>
                    <div class="metric-card"><h3>Gerçekleşen Max Düşüş</h3><h2>{{ metrics['Max Drawdown'] }}</h2></div>
                </div>

                <h2>Monte Carlo Stres Testi ve İflas Riski (10,000 Simülasyon)</h2>
                <div class="metrics-container risk-section">
                    <div class="metric-card"><h3>%95 Güven Aralığı Beklenen Düşüş</h3><h2>{{ metrics.get('95% CI Expected Max Drawdown', 'N/A') }}</h2></div>
                    <div class="metric-card"><h3>%99 Güven Aralığı Beklenen Düşüş</h3><h2>{{ metrics.get('99% CI Expected Max Drawdown', 'N/A') }}</h2></div>
                    <div class="metric-card"><h3>İflas Riski (Risk of Ruin)</h3><h2>{{ metrics.get('Risk of Ruin', 'N/A') }}</h2></div>
                </div>

                <div class="img-container">
                    <h2>Kasa Büyüme Eğrisi (Equity Curve)</h2>
                    <img src="equity_curve.png" alt="Equity Curve">
                </div>

                <div class="footer">
                    CONFIDENTIAL AND PROPRIETARY. This document is for authorized ED Capital personnel only.
                    Distribution or reproduction is strictly prohibited. Generated by ED Capital Quant Engine v2.0.
                </div>
            </div>
        </body>
        </html>
        """

        template = Template(html_template)
        html_content = template.render(
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            metrics=metrics
        )

        report_path = os.path.join(cls.REPORTS_DIR, f'report_{datetime.datetime.now().strftime("%Y%m%d")}.html')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Tear Sheet generated with MC Metrics: {report_path}")
        await async_send_telegram_message(f"📄 <b>Weekly Tear Sheet Generated</b>\nWin Rate: {metrics['Win Rate']}\nPnL: {metrics['Total PnL']}\nRisk of Ruin: {metrics.get('Risk of Ruin', 'N/A')}")

        return report_path
