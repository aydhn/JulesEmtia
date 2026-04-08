import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO
import src.paper_db as db
from src.logger import get_logger
import os

logger = get_logger()

def create_tear_sheet(output_format="html"):
    df = db.get_closed_trades()
    if df.empty:
        logger.info("No closed trades to report.")
        return None

    # Metrics Calculation
    initial_balance = 10000.0
    current_balance = db.get_balance()
    total_pnl = df['pnl'].sum()

    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]
    win_rate = len(wins) / len(df) * 100 if len(df) > 0 else 0

    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0

    # Equity Curve
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['equity'] = initial_balance + df['cumulative_pnl']

    plt.figure(figsize=(10, 5))
    plt.plot(df['exit_time'], df['equity'], label='Equity', color='blue')
    plt.title('Kasa Büyüme Eğrisi')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    equity_img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # HTML Template
    html_content = f"""
    <html>
    <head>
        <title>ED Capital Quant Engine - Performans Raporu</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }}
            .metric-box {{ background: #f7fafc; border: 1px solid #e2e8f0; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .metric-row {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
            .metric-label {{ font-weight: bold; }}
            img {{ max-width: 100%; height: auto; border: 1px solid #e2e8f0; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <h1>Piyasalara Genel Bakış</h1>
        <div class="metric-box">
            <div class="metric-row"><span class="metric-label">Başlangıç Bakiyesi:</span> <span>${initial_balance:.2f}</span></div>
            <div class="metric-row"><span class="metric-label">Güncel Bakiye:</span> <span>${current_balance:.2f}</span></div>
            <div class="metric-row"><span class="metric-label">Net PnL:</span> <span>${total_pnl:.2f}</span></div>
            <div class="metric-row"><span class="metric-label">İsabet Oranı (Win Rate):</span> <span>{win_rate:.2f}%</span></div>
            <div class="metric-row"><span class="metric-label">Kâr Faktörü (Profit Factor):</span> <span>{profit_factor:.2f}</span></div>
            <div class="metric-row"><span class="metric-label">Ortalama Kâr / Zarar:</span> <span>${avg_win:.2f} / ${avg_loss:.2f}</span></div>
        </div>
        <h2>Kasa Büyüme Eğrisi</h2>
        <img src="data:image/png;base64,{equity_img_base64}" alt="Equity Curve">
    </body>
    </html>
    """

    os.makedirs("reports", exist_ok=True)
    report_path = "reports/tear_sheet.html"
    with open(report_path, "w") as f:
        f.write(html_content)

    logger.info(f"Tear sheet generated at {report_path}")
    return report_path
