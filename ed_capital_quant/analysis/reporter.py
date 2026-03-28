import pandas as pd
import matplotlib.pyplot as plt
import os
from typing import Dict
from core.logger import setup_logger
from core.config import REPORTS_DIR

logger = setup_logger("reporter")

class TearSheetGenerator:
    """
    Phase 13: Corporate Reporting & Performance Summary.
    Generates ED Capital standard HTML/PDF Tear Sheets.
    """
    def __init__(self, broker):
        self.broker = broker

    def generate_html_report(self, mc_results: Dict = None) -> str:
        """
        Generates a professional HTML report avoiding amateur terminology.
        """
        closed_trades = self.broker.get_closed_positions()

        if not closed_trades:
            logger.warning("No closed trades to report.")
            return ""

        df = pd.DataFrame(closed_trades)

        # Metrik Hesaplamaları
        initial_balance = self.broker.initial_balance
        current_balance = self.broker.get_account_balance()
        total_pnl = current_balance - initial_balance

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        win_rate = len(wins) / len(df) if len(df) > 0 else 0

        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        # Kümülatif Getiri (Equity Curve)
        df['cumulative_pnl'] = df['pnl'].cumsum() + initial_balance

        # Max Drawdown
        rolling_max = df['cumulative_pnl'].cummax()
        drawdown = (df['cumulative_pnl'] - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100

        # Plot Equity Curve
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(df.index, df['cumulative_pnl'], color='#00ff00', linewidth=2)
        ax.set_title("ED Capital - Portföy Büyüme Eğrisi", fontsize=14, pad=20)
        ax.set_ylabel("Bakiye (USD)")
        ax.grid(True, alpha=0.2)

        img_path = os.path.join(REPORTS_DIR, "equity_curve.png")
        plt.savefig(img_path, bbox_inches='tight', dpi=150)
        plt.close()

        # HTML Şablonu (ED Capital Kurumsal Şablonu)
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; background-color: #f4f7f6; margin: 0; padding: 20px; }}
                .container {{ max-width: 900px; margin: auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                .header {{ border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 30px; }}
                .header h1 {{ color: #2c3e50; margin: 0; font-size: 28px; text-transform: uppercase; letter-spacing: 2px; }}
                h2 {{ color: #34495e; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
                th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #ecf0f1; color: #2c3e50; }}
                .highlight {{ font-weight: bold; color: #27ae60; }}
                .negative {{ font-weight: bold; color: #c0392b; }}
                .chart {{ text-align: center; margin-top: 40px; }}
                .chart img {{ max-width: 100%; border-radius: 4px; border: 1px solid #ddd; }}
                .footer {{ text-align: center; margin-top: 50px; font-size: 12px; color: #7f8c8d; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>ED Capital Quant Engine</h1>
                    <p style="color: #7f8c8d; font-size: 14px;">Kurumsal Performans Raporu (Tear Sheet)</p>
                </div>

                <h2>Piyasalara Genel Bakış</h2>
                <table>
                    <tr><th>Başlangıç Bakiyesi</th><td>${initial_balance:,.2f}</td></tr>
                    <tr><th>Güncel Bakiye</th><td><span class="highlight">${current_balance:,.2f}</span></td></tr>
                    <tr><th>Net PnL (Maliyet Sonrası)</th><td>${total_pnl:,.2f}</td></tr>
                    <tr><th>İsabet Oranı (Win Rate)</th><td>{win_rate:.2%}</td></tr>
                    <tr><th>Kâr Faktörü (Profit Factor)</th><td>{profit_factor:.2f}</td></tr>
                    <tr><th>Ortalama Kâr / Ortalama Zarar</th><td><span class="highlight">${avg_win:,.2f}</span> / <span class="negative">${avg_loss:,.2f}</span></td></tr>
                    <tr><th>Maksimum Düşüş (Max Drawdown)</th><td><span class="negative">{max_drawdown:.2f}%</span></td></tr>
                </table>
        """

        if mc_results:
             html += f"""
                <h2>Stres Testi ve İflas Riski Analizi</h2>
                <table>
                    <tr><th>%99 Güven Aralığında Beklenen Maksimum Düşüş</th><td><span class="negative">{mc_results['var_99']:.2f}%</span></td></tr>
                    <tr><th>İflas Riski (Risk of Ruin - %50 Kayıp)</th><td>{mc_results['risk_of_ruin']:.2%}</td></tr>
                </table>
             """

        html += f"""
                <div class="chart">
                    <h2>Portföy Kümülatif Getiri Eğrisi</h2>
                    <img src="equity_curve.png" alt="Equity Curve">
                </div>

                <div class="footer">
                    <p>Bu rapor ED Capital otonom algoritmik sistemleri tarafından otomatik üretilmiştir.</p>
                </div>
            </div>
        </body>
        </html>
        """

        report_path = os.path.join(REPORTS_DIR, "ed_capital_tear_sheet.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Tear Sheet generated at {report_path}")
        return report_path
