import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Optional

# Conditional import for PDF generation (WeasyPrint can be tricky on some barebone OS)
try:
    from weasyprint import HTML
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from logger import log
import paper_db
from monte_carlo import run_monte_carlo

REPORT_DIR = os.path.join(os.path.dirname(__file__), 'reports')
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

def generate_tear_sheet(initial_capital: float = 10000.0) -> Optional[str]:
    """
    ED Capital Kurumsal Şablonu Tear Sheet Generator (Phase 13).
    Extracts closed trades from SQLite, calculates Quant metrics, generates plots,
    and produces an HTML/PDF Executive Summary report.
    Returns the file path of the generated report.
    """
    try:
        query = "SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time ASC"
        df = paper_db.fetch_dataframe(query)

        if df.empty:
            log.warning("No closed trades available for reporting.")
            return None

        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df.set_index('exit_time', inplace=True)

        # ---------------------------------------------------------
        # 1. CORE QUANT METRICS
        # ---------------------------------------------------------
        total_trades = len(df)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        total_pnl = df['pnl'].sum()
        current_capital = initial_capital + total_pnl

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        # Equity Curve and Drawdown
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['equity'] = initial_capital + df['cumulative_pnl']
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
        max_drawdown = abs(df['drawdown'].min()) * 100

        # ---------------------------------------------------------
        # 2. MONTE CARLO RISK VALIDATION (Phase 22)
        # ---------------------------------------------------------
        mc_results = run_monte_carlo(simulations=5000)

        # ---------------------------------------------------------
        # 3. VISUALIZATIONS (Matplotlib/Seaborn)
        # ---------------------------------------------------------
        plt.style.use('dark_background')
        fig, axes = plt.subplots(2, 1, figsize=(10, 12))

        # Plot 1: Equity Curve
        axes[0].plot(df.index, df['equity'], color='#00ffcc', linewidth=2)
        axes[0].fill_between(df.index, df['equity'], initial_capital, where=(df['equity'] > initial_capital), color='#00ffcc', alpha=0.1)
        axes[0].fill_between(df.index, df['equity'], initial_capital, where=(df['equity'] <= initial_capital), color='#ff3333', alpha=0.1)
        axes[0].set_title('Piyasalara Genel Bakış - Kasa Büyüme Eğrisi', fontsize=14, pad=15)
        axes[0].set_ylabel('Sermaye (USD)')
        axes[0].grid(color='gray', linestyle='--', alpha=0.3)

        # Plot 2: Drawdown Curve
        axes[1].fill_between(df.index, df['drawdown'] * 100, 0, color='#ff3333', alpha=0.4)
        axes[1].plot(df.index, df['drawdown'] * 100, color='#ff3333', linewidth=1.5)
        axes[1].set_title('Maksimum Düşüş (Drawdown) Derinliği', fontsize=14, pad=15)
        axes[1].set_ylabel('Düşüş (%)')
        axes[1].grid(color='gray', linestyle='--', alpha=0.3)

        plot_path = os.path.join(REPORT_DIR, 'equity_curve.png')
        plt.tight_layout()
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        plt.close()

        # ---------------------------------------------------------
        # 4. HTML/PDF GENERATION
        # ---------------------------------------------------------
        # Very basic inline HTML template for 'ED Capital Kurumsal Şablonu'
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; margin: 40px; }}
                h1 {{ color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 10px; }}
                h2 {{ color: #0d47a1; margin-top: 30px; }}
                .metric-box {{ background-color: #f5f5f5; border-left: 5px solid #1a237e; padding: 15px; margin: 10px 0; border-radius: 4px; }}
                .metric-title {{ font-weight: bold; color: #555; text-transform: uppercase; font-size: 12px; }}
                .metric-value {{ font-size: 24px; color: #1a237e; margin-top: 5px; }}
                .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }}
                .footer {{ margin-top: 50px; font-size: 10px; color: #999; text-align: center; border-top: 1px solid #eee; padding-top: 20px; }}
                img {{ max-width: 100%; height: auto; margin-top: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <h1>ED Capital - Piyasalara Genel Bakış (Tear Sheet)</h1>
            <p><strong>Tarih:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>

            <h2>Performans Özeti</h2>
            <div class="grid">
                <div class="metric-box"><div class="metric-title">Başlangıç Bakiyesi</div><div class="metric-value">${initial_capital:,.2f}</div></div>
                <div class="metric-box"><div class="metric-title">Güncel Bakiye</div><div class="metric-value">${current_capital:,.2f}</div></div>
                <div class="metric-box"><div class="metric-title">Net PnL</div><div class="metric-value">${total_pnl:,.2f}</div></div>
                <div class="metric-box"><div class="metric-title">İsabet Oranı (Win Rate)</div><div class="metric-value">{win_rate:.1f}%</div></div>
                <div class="metric-box"><div class="metric-title">Kâr Faktörü (Profit Factor)</div><div class="metric-value">{profit_factor:.2f}</div></div>
                <div class="metric-box"><div class="metric-title">Maksimum Düşüş (Max DD)</div><div class="metric-value">{max_drawdown:.2f}%</div></div>
            </div>

            <h2>Monte Carlo Risk Stres Testi (10.000 Simülasyon)</h2>
            <div class="grid">
                <div class="metric-box"><div class="metric-title">%99 Güven Aralığı Max Drawdown</div><div class="metric-value">{mc_results['max_dd_99']:.2f}%</div></div>
                <div class="metric-box"><div class="metric-title">İflas Riski (Risk of Ruin)</div><div class="metric-value">{mc_results['risk_of_ruin']:.2f}%</div></div>
            </div>

            <h2>Görsel Analiz</h2>
            <img src="{os.path.abspath(plot_path)}" alt="Equity Curve">

            <div class="footer">
                Gizlilik Bildirimi: Bu rapor yalnızca ED Capital iç kullanımı içindir. Yatırım tavsiyesi değildir.<br>
                Sistem: ED Capital Quant Engine v1.0 | Model: Random Forest MTF + VIX Circuit Breaker + Fractional Kelly
            </div>
        </body>
        </html>
        """

        html_path = os.path.join(REPORT_DIR, 'ed_capital_tear_sheet.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        log.info(f"Tear Sheet generated successfully: {html_path}")

        if PDF_SUPPORT:
            pdf_path = os.path.join(REPORT_DIR, 'ed_capital_tear_sheet.pdf')
            HTML(string=html_content, base_url=os.path.dirname(html_path)).write_pdf(pdf_path)
            log.info(f"PDF Report generated successfully: {pdf_path}")
            return pdf_path

        return html_path

    except Exception as e:
        log.error(f"Failed to generate Tear Sheet: {e}")
        return None
