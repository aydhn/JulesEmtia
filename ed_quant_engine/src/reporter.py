import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from src.paper_db import get_closed_trades
from src.logger import get_logger

logger = get_logger("reporter")

# Config
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# CSS for the Tearsheet HTML
CSS = """
<style>
    body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 20px; color: #333; background-color: #f4f6f8; }
    h1 { color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; text-transform: uppercase; font-size: 24px;}
    .metric-container { display: flex; justify-content: space-between; margin-top: 20px; flex-wrap: wrap; }
    .metric-box { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); width: 30%; text-align: center; margin-bottom: 15px; border-left: 4px solid #3182ce;}
    .metric-value { font-size: 28px; font-weight: bold; color: #2b6cb0; margin-top: 10px; }
    .positive { color: #38a169; }
    .negative { color: #e53e3e; }
    .footer { text-align: center; margin-top: 40px; font-size: 12px; color: #718096; }
    table { width: 100%; border-collapse: collapse; margin-top: 30px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
    th { background-color: #2b6cb0; color: white; text-transform: uppercase; font-size: 12px; }
    .chart { margin-top: 30px; text-align: center; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
</style>
"""

def generate_tear_sheet(initial_balance: float = 10000.0) -> str:
    """Generates an HTML Tearsheet summarizing performance."""
    trades = get_closed_trades()

    if not trades:
        logger.warning("No closed trades to generate a report.")
        return ""

    df = pd.DataFrame(trades)
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df.sort_values('exit_time', inplace=True)
    df.set_index('exit_time', inplace=True)

    # 1. Metrics Calculation
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = len(df[df['pnl'] < 0])

    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    gross_profit = df[df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan

    net_profit = df['pnl'].sum()
    current_balance = initial_balance + net_profit

    # Equity Curve Calculation
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['equity'] = initial_balance + df['cumulative_pnl']

    # Drawdown Calculation
    df['running_max'] = df['equity'].cummax()
    df['drawdown'] = (df['equity'] - df['running_max']) / df['running_max']
    max_dd = df['drawdown'].min()

    # 2. Plotting Equity Curve
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df.index, df['equity'], label='Portfolio Value', color='#2b6cb0', linewidth=2)
    ax.fill_between(df.index, df['equity'], initial_balance, where=(df['equity'] >= initial_balance), interpolate=True, color='#38a169', alpha=0.1)
    ax.fill_between(df.index, df['equity'], initial_balance, where=(df['equity'] < initial_balance), interpolate=True, color='#e53e3e', alpha=0.1)

    ax.set_title("Equity Growth Curve", fontsize=14, color='#1a365d')
    ax.set_ylabel("USD Balance")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Save chart
    chart_filename = f"equity_curve_{datetime.now().strftime('%Y%m%d')}.png"
    chart_path = os.path.join(REPORT_DIR, chart_filename)
    plt.savefig(chart_path, dpi=150)
    plt.close()

    # 3. HTML Assembly
    html = f"""
    <html>
    <head><title>ED Capital Quant Engine - Performans Raporu</title>{CSS}</head>
    <body>
        <h1>Piyasalara Genel Bakış (Performance Overview)</h1>

        <div class="metric-container">
            <div class="metric-box">
                <div>Başlangıç Bakiyesi</div>
                <div class="metric-value">${initial_balance:,.2f}</div>
            </div>
            <div class="metric-box">
                <div>Güncel Bakiye</div>
                <div class="metric-value {'positive' if net_profit > 0 else 'negative'}">${current_balance:,.2f}</div>
            </div>
            <div class="metric-box">
                <div>Toplam Net Kâr (PnL)</div>
                <div class="metric-value {'positive' if net_profit > 0 else 'negative'}">${net_profit:,.2f} ({net_profit/initial_balance:.2%})</div>
            </div>
            <div class="metric-box">
                <div>Win Rate (İsabet Oranı)</div>
                <div class="metric-value">{win_rate:.2%}</div>
            </div>
            <div class="metric-box">
                <div>Profit Factor</div>
                <div class="metric-value">{profit_factor:.2f}</div>
            </div>
            <div class="metric-box">
                <div>Max Drawdown</div>
                <div class="metric-value negative">{max_dd:.2%}</div>
            </div>
        </div>

        <div class="chart">
            <img src="{chart_filename}" alt="Equity Curve" style="max-width: 100%; border-radius: 8px;">
        </div>

        <div class="footer">
            Generated by ED Capital Quant Engine (v1.0.0) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC<br>
            Confidential & Proprietary. Not for public distribution.
        </div>
    </body>
    </html>
    """

    # Save HTML
    html_filename = f"ED_Capital_Tearsheet_{datetime.now().strftime('%Y%m%d')}.html"
    html_path = os.path.join(REPORT_DIR, html_filename)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Tearsheet generated at {html_path}")
    return html_path
