import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from .paper_db import get_closed_trades, get_account_balance
from .monte_carlo import run_monte_carlo
from .config import REPORT_DIR
from .logger import log_info, log_error

def generate_tear_sheet() -> str:
    """
    ED Capital Kurumsal Şablonu ile Performans Raporu (Tear Sheet) Üretir.
    HTML ve PDF çıktısı verir. Asla "Yönetici Özeti" ifadesi kullanmaz.
    """
    trades = get_closed_trades()
    if not trades:
        log_error("Raporlanacak kapalı işlem bulunamadı.")
        return ""

    df = pd.DataFrame(trades)

    # --- METRİKLER (Quant Terminology) ---
    total_trades = len(df)
    initial_balance = 10000.0 # Varsayılan
    current_balance = get_account_balance()
    net_pnl = current_balance - initial_balance
    roi_pct = (net_pnl / initial_balance) * 100

    df['pnl_pct'] = df['pnl'] / (df['entry_price'] * df['position_size']) * 100 # Yaklaşık getiri yüzdesi

    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]

    win_rate = (len(wins) / total_trades) * 100

    gross_profit = wins['pnl'].sum() if not wins.empty else 0
    gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')

    avg_win = wins['pnl'].mean() if not wins.empty else 0
    avg_loss = losses['pnl'].mean() if not losses.empty else 0

    # Zaman Serisi Hesaplamaları
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df = df.sort_values('exit_time')
    df['cum_pnl'] = df['pnl'].cumsum() + initial_balance
    df['peak'] = df['cum_pnl'].cummax()
    df['drawdown'] = (df['peak'] - df['cum_pnl']) / df['peak'] * 100
    max_drawdown = df['drawdown'].max()

    # --- MONTE CARLO STRESS TEST ---
    mc_results = run_monte_carlo(trades, initial_balance=initial_balance, n_simulations=10000)
    risk_of_ruin = mc_results.get('RiskOfRuin_50Pct', 0)
    exp_dd_99 = mc_results.get('ExpectedMaxDrawdown_99CI', 0)

    # --- GÖRSELLEŞTİRME (Matplotlib) ---
    os.makedirs(REPORT_DIR, exist_ok=True)
    report_date = datetime.now().strftime("%Y%m%d_%H%M")

    # 1. Equity Curve
    plt.figure(figsize=(10, 5))
    plt.plot(df['exit_time'], df['cum_pnl'], color='#004C99', linewidth=2)
    plt.fill_between(df['exit_time'], df['cum_pnl'], initial_balance, where=(df['cum_pnl'] > initial_balance), color='green', alpha=0.1)
    plt.fill_between(df['exit_time'], df['cum_pnl'], initial_balance, where=(df['cum_pnl'] <= initial_balance), color='red', alpha=0.1)
    plt.title('Kümülatif Portföy Getirisi (Equity Curve)', fontsize=14, fontweight='bold', color='#333333')
    plt.xlabel('Zaman')
    plt.ylabel('Bakiye ($)')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    equity_chart_path = os.path.join(REPORT_DIR, f"equity_{report_date}.png")
    plt.savefig(equity_chart_path)
    plt.close()

    # --- HTML ŞABLONU (ED Capital Kurumsal) ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>ED Capital - Performans Raporu</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 20px; background-color: #f9f9f9; }}
            .container {{ max-width: 900px; margin: auto; background: #fff; padding: 30px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-top: 5px solid #004C99; }}
            h1 {{ color: #004C99; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
            h2 {{ color: #2c3e50; margin-top: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; font-weight: bold; color: #555; }}
            .metric-box {{ background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 5px; padding: 15px; margin-bottom: 20px; text-align: center; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #004C99; }}
            .positive {{ color: #28a745; }}
            .negative {{ color: #dc3545; }}
            .footer {{ text-align: center; margin-top: 40px; font-size: 12px; color: #777; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>ED Capital Quant Engine - Haftalık Performans Raporu</h1>
            <p><strong>Tarih:</strong> {datetime.now().strftime("%d %B %Y, %H:%M")}</p>

            <h2>Piyasalara Genel Bakış</h2>
            <div style="display: flex; justify-content: space-between;">
                <div class="metric-box" style="flex: 1; margin-right: 10px;">
                    <div>Güncel Bakiye</div>
                    <div class="metric-value">${current_balance:,.2f}</div>
                </div>
                <div class="metric-box" style="flex: 1; margin-right: 10px;">
                    <div>Net PnL</div>
                    <div class="metric-value {'positive' if net_pnl > 0 else 'negative'}">${net_pnl:,.2f} ({roi_pct:+.2f}%)</div>
                </div>
                <div class="metric-box" style="flex: 1;">
                    <div>Win Rate</div>
                    <div class="metric-value">{win_rate:.1f}%</div>
                </div>
            </div>

            <h2>Kantitatif Metrikler (Tear Sheet)</h2>
            <table>
                <tr><th>Metrik</th><th>Değer</th><th>Açıklama</th></tr>
                <tr><td>Toplam İşlem</td><td>{total_trades}</td><td>Kapanmış pozisyon sayısı</td></tr>
                <tr><td>Kâr Faktörü (Profit Factor)</td><td>{profit_factor:.2f}</td><td>Brüt Kâr / Brüt Zarar (1.5+ İdealdir)</td></tr>
                <tr><td>Ortalama Kâr (Average Win)</td><td class="positive">${avg_win:.2f}</td><td>Kazançlı işlemlerin ortalaması</td></tr>
                <tr><td>Ortalama Zarar (Average Loss)</td><td class="negative">${avg_loss:.2f}</td><td>Zararlı işlemlerin ortalaması</td></tr>
                <tr><td>Max Drawdown</td><td class="negative">%{max_drawdown:.2f}</td><td>Gerçekleşen en büyük tepe-dip düşüşü</td></tr>
            </table>

            <h2>Risk Yönetimi ve Stres Testi (Monte Carlo 10,000 Simülasyon)</h2>
            <table>
                <tr><th>Risk Metriği</th><th>Değer</th><th>Açıklama</th></tr>
                <tr><td>İflas Riski (Risk of Ruin - 50%)</td><td>%{risk_of_ruin:.2f}</td><td>Kasanın yarısını kaybetme olasılığı</td></tr>
                <tr><td>Beklenen Max Drawdown (%99 Güvenle)</td><td class="negative">%{exp_dd_99:.2f}</td><td>En kötü senaryoda beklenen düşüş</td></tr>
            </table>

            <h2>Portföy Gelişimi</h2>
            <img src="equity_{report_date}.png" style="width: 100%; max-width: 800px; height: auto; border: 1px solid #ddd;">

            <div class="footer">
                Bu rapor ED Capital algoritmik sistemleri tarafından otonom olarak üretilmiştir.<br>
                Geçmiş performans, gelecekteki sonuçların garantisi değildir.
            </div>
        </div>
    </body>
    </html>
    """

    html_path = os.path.join(REPORT_DIR, f"report_{report_date}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    log_info(f"📊 Tear Sheet (Kurumsal Rapor) oluşturuldu: {html_path}")

    # Eğer pdfkit kuruluysa PDF'e çevir (İsteğe bağlı)
    pdf_path = None
    try:
        import pdfkit
        pdf_path = html_path.replace(".html", ".pdf")
        # Base_dir ayarı görselin pdf'e geçmesi için önemlidir
        options = {'enable-local-file-access': None}
        pdfkit.from_file(html_path, pdf_path, options=options)
        log_info(f"📄 PDF Raporu oluşturuldu: {pdf_path}")
    except Exception as e:
        log_warning(f"PDF oluşturulamadı (wkhtmltopdf yüklü olmayabilir), HTML ile devam ediliyor: {e}")

    return pdf_path if pdf_path and os.path.exists(pdf_path) else html_path
