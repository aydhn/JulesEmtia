import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime
from core.telegram_notifier import send_message
from db.paper_broker import PaperBroker

def generate_tear_sheet(broker: PaperBroker):
    cur = broker.conn.cursor()
    cur.execute("SELECT * FROM trades WHERE status='Closed'")
    columns = [column[0] for column in cur.description]
    trades = [dict(zip(columns, row)) for row in cur.fetchall()]

    if not trades:
        send_message("Tear Sheet: İşlem bulunamadı.")
        return

    df = pd.DataFrame(trades)
    df['pnl_pct'] = df['pnl'] / (df['entry_price'] * df['position_size'])

    # Plotting
    plt.figure(figsize=(10,6))
    plt.plot(df['exit_time'], df['pnl_pct'].cumsum(), label='Cumulative PnL')
    plt.title('ED Capital - Piyasalara Genel Bakış (Equity Curve)')
    plt.xlabel('Tarih')
    plt.ylabel('Kümülatif Getiri')
    plt.grid(True, alpha=0.3)
    plt.legend()

    os.makedirs('reports', exist_ok=True)
    img_path = f"reports/tearsheet_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(img_path)
    plt.close()

    # Metrics
    win_rate = len(df[df['pnl'] > 0]) / len(df)
    gross_profit = df[df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

    report_txt = f"""
    📊 ED Capital - Piyasalara Genel Bakış

    Toplam İşlem: {len(df)}
    Win Rate: %{win_rate*100:.2f}
    Profit Factor: {profit_factor:.2f}
    Net PnL: ${df['pnl'].sum():.2f}

    Grafik: {img_path}
    """
    send_message(report_txt)
