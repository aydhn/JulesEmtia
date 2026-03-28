import pandas as pd
import matplotlib.pyplot as plt
import os
from jinja2 import Environment, FileSystemLoader
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config
from ed_quant_engine.core.paper_broker import PaperBroker

logger = setup_logger("Reporter")

class TearSheetGenerator:
    def __init__(self, broker: PaperBroker):
        self.broker = broker
        self.report_dir = Config.REPORT_DIR
        os.makedirs(self.report_dir, exist_ok=True)

        # Jinja setup
        self.env = Environment(loader=FileSystemLoader(self.report_dir))

        # Create HTML Template string if not exists
        template_path = os.path.join(self.report_dir, "template.html")
        if not os.path.exists(template_path):
            with open(template_path, 'w') as f:
                f.write("""
                <html>
                <head>
                    <style>
                        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }
                        h1 { color: #2C3E50; border-bottom: 2px solid #34495E; padding-bottom: 10px; }
                        h2 { color: #2980B9; margin-top: 30px; }
                        .metric-card { background: #ECF0F1; padding: 20px; margin: 10px; border-radius: 8px; display: inline-block; width: 30%; box-sizing: border-box; }
                        .metric-value { font-size: 24px; font-weight: bold; color: #E74C3C; }
                        .positive { color: #27AE60; }
                    </style>
                </head>
                <body>
                    <h1>ED Capital Quant Engine - Piyasalara Genel Bakış</h1>
                    <p><em>Rapor Tarihi: {{ date }}</em></p>

                    <h2>Risk & Getiri Metrikleri</h2>
                    <div>
                        <div class="metric-card">Total PnL<br><span class="metric-value {% if pnl > 0 %}positive{% endif %}">${{ pnl }}</span></div>
                        <div class="metric-card">Win Rate<br><span class="metric-value">{{ win_rate }}%</span></div>
                        <div class="metric-card">Profit Factor<br><span class="metric-value">{{ profit_factor }}</span></div>
                        <div class="metric-card">Max Drawdown (99% CI)<br><span class="metric-value">{{ mdd_99 }}%</span></div>
                        <div class="metric-card">Risk of Ruin<br><span class="metric-value">{{ ror }}%</span></div>
                        <div class="metric-card">Total Trades<br><span class="metric-value">{{ total_trades }}</span></div>
                    </div>

                    <h2>Sistem Performansı Görselleştirme</h2>
                    <img src="monte_carlo.png" width="800" alt="Monte Carlo Simulation">
                </body>
                </html>
                """)

    def generate_tear_sheet(self, mc_results: dict):
        """Generates ED Capital institutional-grade HTML Tear Sheet."""
        df = self.broker.get_closed_trades()
        if df.empty:
            logger.info("No closed trades to report.")
            return None

        # Calculate Metrics
        total_pnl = df['pnl'].sum()
        winners = df[df['pnl'] > 0]
        losers = df[df['pnl'] <= 0]

        win_rate = (len(winners) / len(df)) * 100 if len(df) > 0 else 0
        gross_profit = winners['pnl'].sum() if not winners.empty else 0
        gross_loss = abs(losers['pnl'].sum()) if not losers.empty else 1 # Avoid div by zero
        profit_factor = gross_profit / gross_loss

        # Render HTML
        template = self.env.get_template("template.html")
        html_out = template.render(
            date=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            pnl=round(total_pnl, 2),
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            total_trades=len(df),
            mdd_99=round(mc_results.get('mdd_99', 0), 2),
            ror=round(mc_results.get('risk_of_ruin', 0), 2)
        )

        report_path = os.path.join(self.report_dir, "ed_capital_tear_sheet.html")
        with open(report_path, "w") as f:
            f.write(html_out)

        logger.info(f"Tear Sheet generated at {report_path}")
        return report_path
