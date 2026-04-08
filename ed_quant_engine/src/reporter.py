import pandas as pd
import logging
import sqlite3
import os

logger = logging.getLogger(__name__)

class Reporter:
    """
    Phase 13: ED Capital Kurumsal Tear Sheet Generation
    Generates professional reports (HTML).
    """
    def __init__(self, db_path: str = "paper_db.sqlite3"):
        self.db_path = db_path

    def _get_closed_trades(self) -> pd.DataFrame:
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql("SELECT * FROM trades WHERE status = 'Closed'", conn)
            conn.close()
            return df
        except Exception as e:
            logger.error(f"Failed to fetch trades for report: {e}")
            return pd.DataFrame()

    def generate_tear_sheet(self) -> str:
        df = self._get_closed_trades()
        report_path = "ed_capital_tear_sheet.html"

        if df.empty:
            with open(report_path, "w") as f:
                f.write("<h1>ED Capital - Piyasalara Genel Bakış</h1><p>Henüz tamamlanmış işlem bulunmamaktadır.</p>")
            return report_path

        # Metrics Calculation
        total_pnl = df['pnl'].sum()
        win_trades = df[df['pnl'] > 0]
        loss_trades = df[df['pnl'] <= 0]

        win_rate = len(win_trades) / len(df) if len(df) > 0 else 0
        avg_win = win_trades['pnl'].mean() if not win_trades.empty else 0
        avg_loss = abs(loss_trades['pnl'].mean()) if not loss_trades.empty else 0
        profit_factor = (win_trades['pnl'].sum() / abs(loss_trades['pnl'].sum())) if abs(loss_trades['pnl'].sum()) > 0 else float('inf')

        df['Cumulative_PnL'] = df['pnl'].cumsum()
        df['Peak'] = df['Cumulative_PnL'].cummax()
        df['Drawdown'] = df['Cumulative_PnL'] - df['Peak']
        max_drawdown = df['Drawdown'].min()

        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; color: #333; }}
                .container {{ width: 80%; margin: auto; padding: 20px; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; }}
                .metric-box {{ display: inline-block; width: 30%; padding: 15px; margin: 10px; background-color: #ecf0f1; border-radius: 5px; text-align: center; }}
                .metric-title {{ font-size: 14px; color: #7f8c8d; text-transform: uppercase; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>ED Capital - Piyasalara Genel Bakış</h1>
                <div class="metric-box">
                    <div class="metric-title">Toplam PnL</div>
                    <div class="metric-value">${total_pnl:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Win Rate</div>
                    <div class="metric-value">{win_rate:.2%}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Profit Factor</div>
                    <div class="metric-value">{profit_factor:.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Maksimum Düşüş (Max DD)</div>
                    <div class="metric-value">${max_drawdown:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Ortalama Kâr</div>
                    <div class="metric-value">${avg_win:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-title">Ortalama Zarar</div>
                    <div class="metric-value">$-{avg_loss:,.2f}</div>
                </div>
                <p>Not: Rapor otomatik olarak ED Capital Quant Engine tarafından üretilmiştir.</p>
            </div>
        </body>
        </html>
        """

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear sheet successfully generated at {report_path}")
        return report_path
