import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pdfkit
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime
from ed_quant_engine.core.logger import logger
from ed_quant_engine.notifications.notifier import send_document

class EDReporter:
    """
    Tear Sheet / Professional Reporting Generator.
    Produces high-quality HTML/PDF reports compliant with ED Capital standards.
    """
    def __init__(self, db_path: str = "paper_db.sqlite3"):
        self.db_path = db_path
        self.output_dir = "reports"
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch_closed_trades(self) -> pd.DataFrame:
        import sqlite3
        try:
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed'", conn)
        except Exception as e:
            logger.error(f"Reporting: DB Fetch Error: {e}")
            return pd.DataFrame()

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        if df.empty:
            return {"Total PnL": 0.0, "Win Rate": 0.0, "Profit Factor": 0.0, "Max Drawdown": 0.0}

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] < 0]

        gross_profit = wins['pnl'].sum() if not wins.empty else 0.0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0.0

        win_rate = len(wins) / len(df) * 100
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Cumulative PnL to calculate Drawdown
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['peak'] = df['cumulative_pnl'].cummax()
        df['drawdown'] = df['cumulative_pnl'] - df['peak']

        # Max Drawdown (Relative to peak)
        max_drawdown = df['drawdown'].min()

        return {
            "Total PnL": df['pnl'].sum(),
            "Win Rate": f"{win_rate:.2f}%",
            "Profit Factor": f"{profit_factor:.2f}",
            "Max Drawdown": f"{max_drawdown:.2f}",
            "Average Win": f"{wins['pnl'].mean() if not wins.empty else 0.0:.2f}",
            "Average Loss": f"{losses['pnl'].mean() if not losses.empty else 0.0:.2f}"
        }

    def generate_equity_curve(self, df: pd.DataFrame, filename: str = "equity_curve.png"):
        """
        Creates the equity curve plot for the report.
        """
        if df.empty:
            return

        plt.figure(figsize=(10, 5))
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df.set_index('exit_time', inplace=True)

        # Basic equity curve starting from 0
        df['cumulative_pnl'].plot(title="ED Capital Quant Engine - Kümülatif Kâr/Zarar Eğrisi", color='blue')
        plt.xlabel("Tarih")
        plt.ylabel("Kâr/Zarar (USD)")
        plt.grid(True, linestyle='--', alpha=0.6)

        path = os.path.join(self.output_dir, filename)
        plt.savefig(path)
        plt.close()
        return path

    def create_tear_sheet(self):
        """
        Generates the final HTML/PDF report.
        Strict formatting rule: Main summary header is "Piyasalara Genel Bakış".
        """
        df = self.fetch_closed_trades()
        metrics = self.calculate_metrics(df)

        # Generate Charts
        img_path = self.generate_equity_curve(df)

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                h1 {{ color: #0a2342; border-bottom: 2px solid #0a2342; padding-bottom: 10px; }}
                h2 {{ color: #173f5f; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; color: #333; }}
                .metric-box {{ display: inline-block; width: 30%; background: #f9f9f9; padding: 15px; margin: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .metric-title {{ font-size: 14px; color: #666; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #0a2342; }}
            </style>
        </head>
        <body>
            <h1>ED Capital Quant Engine Performans Raporu</h1>
            <p><strong>Tarih:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

            <h2>Piyasalara Genel Bakış</h2>
            <div>
                <div class="metric-box">
                    <div class="metric-title">Toplam Net Kâr/Zarar</div>
                    <div class="metric-value">${metrics['Total PnL']:.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">İsabet Oranı (Win Rate)</div>
                    <div class="metric-value">{metrics['Win Rate']}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Kâr Faktörü (Profit Factor)</div>
                    <div class="metric-value">{metrics['Profit Factor']}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Maksimum Düşüş (Max Drawdown)</div>
                    <div class="metric-value">${metrics['Max Drawdown']}</div>
                </div>
            </div>

            <h2>Kasa Büyüme Eğrisi (Equity Curve)</h2>
            <img src="{os.path.abspath(img_path) if img_path else ''}" style="max-width: 100%;" />

            <h2>Son İşlemler</h2>
            <table>
                <tr>
                    <th>Tarih</th>
                    <th>Varlık</th>
                    <th>Yön</th>
                    <th>Giriş</th>
                    <th>Çıkış</th>
                    <th>Kâr/Zarar</th>
                </tr>
                {"".join([f"<tr><td>{row['exit_time'][:10]}</td><td>{row['ticker']}</td><td>{row['direction']}</td><td>{row['entry_price']:.4f}</td><td>{row['exit_price']:.4f}</td><td>${row['pnl']:.2f}</td></tr>" for _, row in df.tail(10).iterrows()]) if not df.empty else "<tr><td colspan='6'>İşlem bulunamadı.</td></tr>"}
            </table>
        </body>
        </html>
        """

        report_html = os.path.join(self.output_dir, f"ED_Report_{datetime.now().strftime('%Y%m%d')}.html")
        with open(report_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet Generated: {report_html}")
        send_document(report_html, caption="📊 ED Capital Haftalık Performans Raporu")

        # PDF conversion requires wkhtmltopdf installed on the OS.
        # pdfkit.from_file(report_html, report_html.replace('.html', '.pdf'))
