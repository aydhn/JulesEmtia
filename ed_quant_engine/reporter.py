import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import datetime
from logger import log
import paper_db as db
from config import INITIAL_CAPITAL
from notifier import notifier

def generate_tear_sheet(send_to_telegram: bool = True):
    """
    Generates a professional Tear Sheet (Performance Report)
    Adhering to ED Capital Corporate Standards.
    """
    log.info("Generating Tear Sheet...")

    # Fetch Data
    trades_df = db.get_all_trades_df()
    if trades_df.empty:
        log.warning("No trades available for report.")
        return

    closed_trades = trades_df[trades_df['status'] == 'Closed'].copy()
    if closed_trades.empty:
        return

    # Metrics
    total_trades = len(closed_trades)
    winning_trades = closed_trades[closed_trades['pnl'] > 0]
    losing_trades = closed_trades[closed_trades['pnl'] <= 0]

    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    gross_profit = winning_trades['pnl'].sum()
    gross_loss = abs(losing_trades['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_pnl = gross_profit - gross_loss
    current_balance = INITIAL_CAPITAL + net_pnl

    avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0

    # Formatting
    report_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; }}
            .header {{ background-color: #1a237e; color: white; padding: 20px; text-align: center; }}
            .section {{ margin: 20px; padding: 20px; border: 1px solid #eee; border-radius: 5px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; border-bottom: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ED CAPITAL QUANT ENGINE</h1>
            <h2>Piyasalara Genel Bakış (Performance Report)</h2>
            <p>Tarih: {datetime.datetime.now().strftime("%Y-%m-%d")}</p>
        </div>

        <div class="section">
            <h3>Performans Metrikleri</h3>
            <table>
                <tr><th>Başlangıç Bakiyesi</th><td>${INITIAL_CAPITAL:,.2f}</td></tr>
                <tr><th>Güncel Bakiye</th><td>${current_balance:,.2f}</td></tr>
                <tr><th>Toplam Net Kâr/Zarar</th><td>${net_pnl:,.2f}</td></tr>
                <tr><th>İşlem Sayısı</th><td>{total_trades}</td></tr>
                <tr><th>İsabet Oranı (Win Rate)</th><td>{win_rate:.2%}</td></tr>
                <tr><th>Kâr Faktörü (Profit Factor)</th><td>{profit_factor:.2f}</td></tr>
                <tr><th>Ortalama Kâr / Zarar</th><td>${avg_win:,.2f} / ${avg_loss:,.2f}</td></tr>
            </table>
        </div>
    </body>
    </html>
    """

    file_path = f"data/ED_Capital_TearSheet_{datetime.datetime.now().strftime('%Y%m%d')}.html"
    with open(file_path, "w", encoding='utf-8') as f:
        f.write(report_html)

    log.info(f"Tear Sheet generated at {file_path}")

    if send_to_telegram:
        notifier.send_document(file_path, caption="📊 Haftalık Piyasalara Genel Bakış Raporu")
