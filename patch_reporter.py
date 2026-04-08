import re

with open("ed_quant_engine/src/reporter.py", "r") as f:
    content = f.read()

imports = """
import pandas as pd
import sqlite3
import logging
from datetime import datetime
import os
import io
import base64
import matplotlib.pyplot as plt
import seaborn as sns
from src.config import DB_PATH
"""
content = re.sub(r"import pandas as pd.*?from src.config import DB_PATH", imports.strip(), content, flags=re.DOTALL)

new_logic = """
    def create_equity_curve_b64(self, df: pd.DataFrame) -> str:
        if df.empty: return ""
        df = df.copy()
        df['Cumulative_PnL'] = df['pnl'].cumsum()

        plt.figure(figsize=(10, 4))
        plt.plot(pd.to_datetime(df['exit_time']), df['Cumulative_PnL'], color='#0b1a30', linewidth=2)
        plt.title("Kasa Büyüme Eğrisi (Equity Curve)", fontsize=14, color='#0b1a30')
        plt.xlabel("Tarih")
        plt.ylabel("Kümülatif Kâr/Zarar ($)")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')

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

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        # Calculate Drawdown
        df_sorted = df.sort_values('exit_time')
        df_sorted['cumulative_pnl'] = df_sorted['pnl'].cumsum()
        df_sorted['high_water_mark'] = df_sorted['cumulative_pnl'].cummax()
        df_sorted['drawdown'] = df_sorted['cumulative_pnl'] - df_sorted['high_water_mark']
        max_drawdown = df_sorted['drawdown'].min()

        eq_curve_img = self.create_equity_curve_b64(df_sorted)
        img_tag = f'<img src="data:image/png;base64,{eq_curve_img}" style="width:100%; max-width:800px;">' if eq_curve_img else ""

        # Generate HTML
        html = f\"\"\"
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; }}
                .header {{ background-color: #0b1a30; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; max-width: 900px; margin: 0 auto; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; border-bottom: 1px solid #ddd; text-align: left; }}
                th {{ background-color: #f2f2f2; color: #0b1a30; }}
                .img-container {{ text-align: center; margin-top: 30px; margin-bottom: 30px; }}
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
                    <tr><td>Maksimum Düşüş (Max Drawdown)</td><td>${abs(max_drawdown):.2f}</td></tr>
                    <tr><td>Ortalama Kâr / Ortalama Zarar</td><td>${avg_win:.2f} / ${abs(avg_loss):.2f}</td></tr>
                </table>

                <div class="img-container">
                    {img_tag}
                </div>
            </div>
        </body>
        </html>
        \"\"\"

        report_path = f"reports/tear_sheet_{datetime.now().strftime('%Y%m%d')}.html"
"""

old_logic = """
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
        html = f\"\"\"
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
        \"\"\"

        report_path = f"reports/tear_sheet_{datetime.now().strftime('%Y%m%d')}.html"
"""

content = content.replace(old_logic.strip(), new_logic.strip())

with open("ed_quant_engine/src/reporter.py", "w") as f:
    f.write(content)
