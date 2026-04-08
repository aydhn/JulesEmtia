import pandas as pd
import sqlite3
import logging
from datetime import datetime
import os
from src.config import DB_PATH

logger = logging.getLogger(__name__)

class Reporter:
    """
    Phase 13: Kurumsal Raporlama (ED Capital Standartları)
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def fetch_closed_trades(self) -> pd.DataFrame:
        if not os.path.exists(self.db_path):
            return pd.DataFrame()
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql("SELECT * FROM trades WHERE status = 'Closed'", conn)
        conn.close()
        return df

    def generate_html_report(self) -> str:
        df = self.fetch_closed_trades()
        if df.empty:
            return "<html><body><h2>Piyasalara Genel Bakış</h2><p>Henüz kapanmış işlem yok.</p></body></html>"

        total_trades = len(df)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
        net_pnl = gross_profit - gross_loss

        # Generate HTML (Avoiding heavy matplotlib for now to keep it lightweight)
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; }}
                .header {{ background-color: #0b1a30; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>ED Capital Quant Engine</h1>
                <h2>Piyasalara Genel Bakış</h2>
                <p>Tarih: {datetime.now().strftime("%Y-%m-%d")}</p>
            </div>
            <div class="content">
                <h3>Performans Metrikleri</h3>
                <table>
                    <tr><th>Metrik</th><th>Değer</th></tr>
                    <tr><td>Toplam İşlem</td><td>{total_trades}</td></tr>
                    <tr><td>Net Kâr (PnL)</td><td>${net_pnl:.2f}</td></tr>
                    <tr><td>İsabet Oranı (Win Rate)</td><td>{win_rate*100:.1f}%</td></tr>
                    <tr><td>Kâr Faktörü (Profit Factor)</td><td>{profit_factor:.2f}</td></tr>
                </table>
            </div>
        </body>
        </html>
        """

        report_path = f"reports/tear_sheet_{datetime.now().strftime('%Y%m%d')}.html"
        os.makedirs("reports", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Tear sheet generated: {report_path}")
        return report_path
