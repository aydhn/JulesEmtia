import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from jinja2 import Environment, FileSystemLoader
import pdfkit
import os
from paper_db import get_closed_trades
from logger import get_logger

log = get_logger()

# Setup paths
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)
TEMPLATE_DIR = "templates"
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# Generate default template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ED Capital Quant Engine - Piyasalara Genel Bakış</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 40px; }
        h1 { color: #002855; border-bottom: 2px solid #002855; padding-bottom: 10px; }
        .metric-box { background: #f4f7f6; padding: 20px; margin: 10px; border-radius: 5px; width: 30%; display: inline-block; text-align: center; }
        .metric-value { font-size: 24px; font-weight: bold; color: #002855; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #002855; color: white; }
    </style>
</head>
<body>
    <h1>Piyasalara Genel Bakış (Yönetici Özeti)</h1>
    <p>Rapor Tarihi: {{ date }}</p>

    <div>
        <div class="metric-box">
            <div>Toplam Net PnL</div>
            <div class="metric-value">{{ total_pnl }} USD</div>
        </div>
        <div class="metric-box">
            <div>İsabet Oranı (Win Rate)</div>
            <div class="metric-value">{{ win_rate }}%</div>
        </div>
        <div class="metric-box">
            <div>Kâr Faktörü (Profit Factor)</div>
            <div class="metric-value">{{ profit_factor }}</div>
        </div>
    </div>

    <h2>Risk Analizi (Monte Carlo %99 Güven Aralığı)</h2>
    <ul>
        <li>Beklenen Maksimum Düşüş: <b>{{ max_dd_99 }}%</b></li>
        <li>İflas Riski (Risk of Ruin): <b>{{ risk_of_ruin }}%</b></li>
    </ul>

    <h2>Performans Eğrisi</h2>
    <img src="equity_curve.png" width="800">
</body>
</html>
"""

with open(f"{TEMPLATE_DIR}/tearsheet.html", "w", encoding="utf-8") as f:
    f.write(HTML_TEMPLATE)

def generate_tear_sheet(monte_carlo_results: dict = None):
    """
    Generates a professional Tear Sheet (HTML/PDF) in ED Capital Corporate Template.
    Calculates Win Rate, Profit Factor, and plots Equity Curve.
    """
    trades = get_closed_trades(limit=1000)
    if not trades:
        log.warning("No closed trades to generate report.")
        return None

    df = pd.DataFrame(trades, columns=['id', 'ticker', 'dir', 'en_time', 'en_price', 'sl', 'tp', 'qty', 'status', 'ex_time', 'ex_price', 'pnl', 'cost'])

    total_pnl = df['pnl'].sum()
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]

    win_rate = (len(wins) / len(df)) * 100 if len(df) > 0 else 0

    gross_win = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else float('inf')

    # Plot Equity Curve
    df['cumulative_pnl'] = df['pnl'].cumsum()
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df['cumulative_pnl'], color='#002855', linewidth=2)
    plt.title("ED Capital Kümülatif Getiri Eğrisi")
    plt.xlabel("Trade Count")
    plt.ylabel("Cumulative PnL (USD)")
    plt.grid(True, alpha=0.3)

    img_path = f"{REPORTS_DIR}/equity_curve.png"
    plt.savefig(img_path, bbox_inches='tight')
    plt.close()

    # Generate HTML
    env = FileSystemLoader(TEMPLATE_DIR)
    template = Environment(loader=env).get_template("tearsheet.html")

    mc = monte_carlo_results or {"max_dd_99": 0, "risk_of_ruin": 0}

    html_out = template.render(
        date=pd.Timestamp.now().strftime("%Y-%m-%d"),
        total_pnl=f"{total_pnl:.2f}",
        win_rate=f"{win_rate:.1f}",
        profit_factor=f"{profit_factor:.2f}",
        max_dd_99=f"{mc.get('max_dd_99', 0) * 100:.1f}",
        risk_of_ruin=f"{mc.get('risk_of_ruin', 0) * 100:.2f}"
    )

    html_path = f"{REPORTS_DIR}/latest_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    log.info(f"Tear sheet generated at {html_path}")
    return html_path
