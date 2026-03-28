import pandas as pd
from core.paper_db import db
from utils.logger import log
from analytics.monte_carlo import run_monte_carlo

def generate_tear_sheet(output_file="report.html") -> str:
    log.info("ED Capital Tear Sheet Hazırlanıyor...")

    closed_trades = db.get_closed_trades()

    if closed_trades.empty:
        log.warning("Kapanmış işlem bulunamadı. Boş rapor üretiliyor.")
        win_rate = 0.0
        profit_factor = 0.0
        total_pnl = 0.0
        mdd_99 = 0.0
        risk_of_ruin = 0.0
    else:
        wins = closed_trades[closed_trades['pnl'] > 0]
        losses = closed_trades[closed_trades['pnl'] < 0]

        win_rate = len(wins) / len(closed_trades) * 100
        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 999
        total_pnl = closed_trades['pnl'].sum()

        # Phase 22: Monte Carlo Risk Metrics
        mc_results = run_monte_carlo(closed_trades)
        risk_of_ruin = mc_results.get("Risk_of_Ruin", 0) * 100
        mdd_99 = mc_results.get("Expected_MDD_99", 0) * 100

    html_content = f"""
    <html>
    <head><title>ED Capital - Piyasalara Genel Bakış</title></head>
    <style>
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #f8f9fa; color: #333; margin: 40px; }}
        h1 {{ color: #004080; border-bottom: 2px solid #004080; padding-bottom: 10px; }}
        .metric-box {{ background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .metric-title {{ font-weight: bold; font-size: 1.2em; color: #555; }}
        .metric-value {{ font-size: 2em; color: #004080; font-weight: bold; }}
    </style>
    <body>
    <h1>ED Capital - Piyasalara Genel Bakış</h1>
    <p>Otonom Algoritmik İşlem Motoru Performans Raporu.</p>

    <div class="metric-box">
        <div class="metric-title">Toplam Net PnL (Spread + Slippage Dahil)</div>
        <div class="metric-value">${total_pnl:.2f}</div>
    </div>

    <div class="metric-box">
        <div class="metric-title">İsabet Oranı (Win Rate)</div>
        <div class="metric-value">{win_rate:.1f}%</div>
    </div>

    <div class="metric-box">
        <div class="metric-title">Kâr Faktörü (Profit Factor)</div>
        <div class="metric-value">{profit_factor:.2f}</div>
    </div>

    <div class="metric-box">
        <div class="metric-title">%99 Güven Aralığında Beklenen Maksimum Düşüş (Monte Carlo MDD)</div>
        <div class="metric-value">{mdd_99:.2f}%</div>
    </div>

    <div class="metric-box">
        <div class="metric-title">İflas Riski (Risk of Ruin - Monte Carlo)</div>
        <div class="metric-value">{risk_of_ruin:.2f}%</div>
    </div>

    </body>
    </html>
    """

    with open(output_file, "w", encoding='utf-8') as f:
        f.write(html_content)

    log.info(f"Tear Sheet oluşturuldu: {output_file}")
    return output_file
