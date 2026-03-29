import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime
from ed_quant_engine.logger import log
from ed_quant_engine.paper_db import get_all_closed_trades
from ed_quant_engine.config import REPORTS_DIR, INITIAL_CAPITAL
from ed_quant_engine.notifier import send_telegram_message

def generate_tear_sheet() -> str:
    """Generates an ED Capital formatted HTML Tear Sheet and sends to Telegram."""
    df = get_all_closed_trades()

    if df.empty:
        log.warning("No closed trades to report.")
        return ""

    df['entry_time'] = pd.to_datetime(df['entry_time'])
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df.sort_values('exit_time', inplace=True)

    # 1. Calculate Metrics
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    losing_trades = len(df[df['pnl'] <= 0])

    win_rate = winning_trades / total_trades if total_trades > 0 else 0

    gross_profit = df[df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df[df['pnl'] <= 0]['pnl'].sum())

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_pnl = gross_profit - gross_loss

    avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
    avg_loss = df[df['pnl'] <= 0]['pnl'].mean() if losing_trades > 0 else 0

    # Equity Curve
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['equity'] = INITIAL_CAPITAL + df['cumulative_pnl']

    # Max Drawdown
    df['peak'] = df['equity'].cummax()
    df['drawdown'] = (df['equity'] - df['peak']) / df['peak']
    max_drawdown = df['drawdown'].min()

    # 2. Visualizations
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Equity Curve Plot
    ax1.plot(df['exit_time'], df['equity'], color='#00ff00', linewidth=2)
    ax1.fill_between(df['exit_time'], df['equity'], INITIAL_CAPITAL, alpha=0.1, color='#00ff00')
    ax1.set_title('ED Capital - Kümülatif Kasa Büyüme Eğrisi', fontsize=14, pad=15)
    ax1.set_ylabel('Portföy Değeri (USD)')
    ax1.grid(True, alpha=0.2)

    # Drawdown Plot
    ax2.plot(df['exit_time'], df['drawdown'] * 100, color='#ff0000', linewidth=1.5)
    ax2.fill_between(df['exit_time'], df['drawdown'] * 100, 0, alpha=0.3, color='#ff0000')
    ax2.set_title('Maksimum Düşüş (Drawdown %)', fontsize=14, pad=15)
    ax2.set_ylabel('Düşüş (%)')
    ax2.grid(True, alpha=0.2)

    plt.tight_layout()
    plot_path = os.path.join(REPORTS_DIR, f"equity_curve_{datetime.now().strftime('%Y%m%d')}.png")
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()

    # 3. HTML Report Generation (ED Capital Format)
    html_content = f"""
    <html>
    <head>
        <title>ED Capital Quant Engine - Performans Raporu</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #1a1a1a; color: #ffffff; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: auto; background-color: #262626; padding: 40px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }}
            h1 {{ color: #d4af37; text-align: center; border-bottom: 2px solid #d4af37; padding-bottom: 15px; font-weight: 300; letter-spacing: 2px; }}
            h2 {{ color: #00ff00; font-weight: 400; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 40px; }}
            .metric-box {{ background-color: #333; padding: 20px; border-radius: 5px; border-left: 4px solid #d4af37; }}
            .metric-label {{ font-size: 0.9em; color: #aaaaaa; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }}
            .metric-value {{ font-size: 1.5em; font-weight: bold; }}
            .positive {{ color: #00ff00; }}
            .negative {{ color: #ff4444; }}
            .chart-container {{ text-align: center; margin-top: 30px; }}
            .chart-container img {{ max-width: 100%; border-radius: 5px; border: 1px solid #444; }}
            .footer {{ text-align: center; margin-top: 40px; font-size: 0.8em; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ED CAPITAL QUANT ENGINE</h1>
            <h2>Piyasalara Genel Bakış</h2>

            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-label">Başlangıç Bakiyesi</div>
                    <div class="metric-value">${INITIAL_CAPITAL:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Güncel Bakiye</div>
                    <div class="metric-value ${'positive' if net_pnl > 0 else 'negative'}">${INITIAL_CAPITAL + net_pnl:,.2f}</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">Net PnL</div>
                    <div class="metric-value ${'positive' if net_pnl > 0 else 'negative'}">${net_pnl:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">İsabet Oranı (Win Rate)</div>
                    <div class="metric-value">{win_rate:.2%}</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">Kâr Faktörü (Profit Factor)</div>
                    <div class="metric-value">{profit_factor:.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Maksimum Düşüş (Max Drawdown)</div>
                    <div class="metric-value negative">{max_drawdown:.2%}</div>
                </div>

                <div class="metric-box">
                    <div class="metric-label">Ortalama Kâr (Avg Win)</div>
                    <div class="metric-value positive">${avg_win:,.2f}</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Ortalama Zarar (Avg Loss)</div>
                    <div class="metric-value negative">${avg_loss:,.2f}</div>
                </div>
            </div>

            <div class="chart-container">
                <img src="{os.path.basename(plot_path)}" alt="Equity Curve">
            </div>

            <div class="footer">
                <p>Bu rapor ED Capital Quant Engine tarafından otonom olarak üretilmiştir. Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p>SPL Düzey 3 Denetim Standartlarına Uygun Olarak Kayıt Altına Alınmıştır.</p>
            </div>
        </div>
    </body>
    </html>
    """

    report_path = os.path.join(REPORTS_DIR, f"tear_sheet_{datetime.now().strftime('%Y%m%d')}.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    log.info(f"Tear Sheet generated at {report_path}")

    # Send Telegram Summary
    summary = (
        f"📊 <b>Piyasalara Genel Bakış (Haftalık Özet)</b>\n\n"
        f"<b>Güncel Kasa:</b> ${INITIAL_CAPITAL + net_pnl:,.2f}\n"
        f"<b>Net PnL:</b> ${net_pnl:,.2f}\n"
        f"<b>Win Rate:</b> {win_rate:.2%}\n"
        f"<b>Profit Factor:</b> {profit_factor:.2f}\n"
        f"<b>Max Drawdown:</b> {max_drawdown:.2%}\n\n"
        f"<i>Detaylı HTML raporu sunucuya kaydedildi.</i>"
    )
    send_telegram_message(summary)
    return report_path

if __name__ == "__main__":
    import pandas as pd # needed for Timestamp in broker
    generate_tear_sheet()
