import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from paper_db import get_closed_trades
from utils.logger import setup_logger
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from monte_carlo import run_monte_carlo_simulation

logger = setup_logger("Reporter")

# Create templates dir
TEMPLATES_DIR = "templates"
if not os.path.exists(TEMPLATES_DIR):
    os.makedirs(TEMPLATES_DIR)

REPORT_DIR = "reports"
if not os.path.exists(REPORT_DIR):
    os.makedirs(REPORT_DIR)

# HTML Template (ED Capital Style) integrating Monte Carlo
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Piyasalara Genel Bakış - ED Capital</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; margin: 40px; }
        .header { text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-bottom: 30px; }
        .header h1 { color: #2c3e50; margin: 0; font-size: 28px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 40px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
        .metric-card h3 { margin: 0 0 10px 0; color: #7f8c8d; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }
        .metric-card p { margin: 0; font-size: 24px; font-weight: bold; color: #2c3e50; }
        .positive { color: #27ae60 !important; }
        .negative { color: #c0392b !important; }

        .mc-section { background: #e8f4f8; padding: 20px; border-radius: 8px; margin-bottom: 40px; border-left: 5px solid #2980b9;}
        .mc-section h2 { color: #2c3e50; margin-top: 0; }

        .charts { text-align: center; margin-top: 40px; }
        .charts img { max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .footer { text-align: center; margin-top: 50px; font-size: 12px; color: #95a5a6; }
    </style>
</head>
<body>
    <div class="header">
        <h1>ED Capital Quant Engine - Piyasalara Genel Bakış</h1>
        <p>Tarih: {{ date }}</p>
    </div>

    <div class="metrics-grid">
        <div class="metric-card"><h3>Başlangıç Bakiyesi</h3><p>${{ initial_balance }}</p></div>
        <div class="metric-card"><h3>Güncel Bakiye</h3><p>${{ current_balance }}</p></div>
        <div class="metric-card"><h3>Toplam Net PnL</h3><p class="{% if net_pnl > 0 %}positive{% else %}negative{% endif %}">${{ net_pnl }}</p></div>
        <div class="metric-card"><h3>İsabet Oranı (Win Rate)</h3><p>{{ win_rate }}%</p></div>

        <div class="metric-card"><h3>Kâr Faktörü</h3><p>{{ profit_factor }}</p></div>
        <div class="metric-card"><h3>Max Drawdown</h3><p class="negative">{{ max_drawdown }}%</p></div>
        <div class="metric-card"><h3>Ortalama Kâr</h3><p class="positive">${{ avg_win }}</p></div>
        <div class="metric-card"><h3>Ortalama Zarar</h3><p class="negative">${{ avg_loss }}</p></div>
    </div>

    <div class="mc-section">
        <h2>Monte Carlo Stres Testi (10,000 Simülasyon)</h2>
        <p><strong>%99 Güven Aralığında Beklenen Max Drawdown:</strong> <span class="negative">{{ mc_var99 }}%</span></p>
        <p><strong>İflas Riski (Risk of Ruin - %50 Kayıp İhtimali):</strong> <span class="{% if mc_ruin > 1 %}negative{% else %}positive{% endif %}">{{ mc_ruin }}%</span></p>
    </div>

    <div class="charts">
        <h2>Kasa Büyüme Eğrisi (Equity Curve)</h2>
        <img src="{{ equity_curve_path }}" alt="Equity Curve">

        {% if mc_chart_path %}
        <h2>Monte Carlo Simülasyonu (Spaghetti Plot)</h2>
        <img src="{{ mc_chart_path }}" alt="Monte Carlo">
        {% endif %}
    </div>

    <div class="footer">
        <p>ED Capital Quant Engine. Tüm veriler kağıt üstünde simüle edilmiş net maliyet (Slippage + Spread) sonrası değerlerdir.</p>
    </div>
</body>
</html>
"""

with open(os.path.join(TEMPLATES_DIR, "tear_sheet.html"), "w", encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

def generate_tear_sheet(initial_balance: float = 10000.0) -> str:
    """Generates a professional HTML Tear Sheet integrating historical trade data and Monte Carlo simulations."""
    try:
        df = get_closed_trades()
        if df.empty:
            logger.warning("Raporlanacak kapalı işlem bulunamadı.")
            return ""

        total_trades = len(df)
        winning_trades = df[df['pnl'] > 0]
        losing_trades = df[df['pnl'] <= 0]

        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        gross_profit = winning_trades['pnl'].sum()
        gross_loss = abs(losing_trades['pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
        net_pnl = df['pnl'].sum()
        current_balance = initial_balance + net_pnl
        avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
        avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0

        # Equity Curve
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['equity'] = initial_balance + df['cumulative_pnl']
        df['peak'] = df['equity'].cummax()
        df['drawdown'] = (df['equity'] - df['peak']) / df['peak'] * 100
        max_drawdown = df['drawdown'].min()

        # Equity Curve Chart
        plt.figure(figsize=(10, 5))
        plt.plot(df.index, df['equity'], color='#2980b9', linewidth=2)
        plt.fill_between(df.index, df['equity'], initial_balance, where=(df['equity'] >= initial_balance), interpolate=True, color='#2ecc71', alpha=0.3)
        plt.fill_between(df.index, df['equity'], initial_balance, where=(df['equity'] < initial_balance), interpolate=True, color='#e74c3c', alpha=0.3)
        plt.title('Equity Curve (Net of Fees)', fontsize=14, color='#2c3e50')
        plt.ylabel('Sermaye ($)')
        plt.xlabel('İşlem Sırası')
        plt.grid(True, linestyle='--', alpha=0.6)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        equity_chart = f"equity_{timestamp}.png"
        plt.tight_layout()
        plt.savefig(os.path.join(REPORT_DIR, equity_chart))
        plt.close()

        # Run Monte Carlo (Phase 22 Integration)
        mc_results = run_monte_carlo_simulation(10000)
        mc_var99 = f"{abs(mc_results.get('var_99', 0)):.2f}"
        mc_ruin = f"{mc_results.get('risk_of_ruin', 0):.2f}"
        mc_chart = os.path.basename(mc_results.get('chart_path', '')) if 'chart_path' in mc_results else ""

        # Render HTML
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        template = env.get_template('tear_sheet.html')

        html_content = template.render(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            initial_balance=f"{initial_balance:,.2f}",
            current_balance=f"{current_balance:,.2f}",
            net_pnl=f"{net_pnl:,.2f}",
            win_rate=f"{win_rate:.1f}",
            profit_factor=f"{profit_factor:.2f}",
            max_drawdown=f"{abs(max_drawdown):.2f}",
            avg_win=f"{avg_win:.2f}",
            avg_loss=f"{abs(avg_loss):.2f}",
            equity_curve_path=equity_chart,
            mc_var99=mc_var99,
            mc_ruin=mc_ruin,
            mc_chart_path=mc_chart
        )

        report_filename = f"tear_sheet_{timestamp}.html"
        report_path = os.path.join(REPORT_DIR, report_filename)

        with open(report_path, "w", encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Tear Sheet Raporu Oluşturuldu: {report_path}")
        return report_path

    except Exception as e:
        logger.error(f"Rapor oluşturma hatası: {str(e)}")
        return ""
