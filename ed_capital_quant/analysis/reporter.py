import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import io
import base64
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import pdfkit

from core.logger import logger
from core.database import fetch_dataframe

REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

class PerformanceReporter:
    """ED Capital Kurumsal Standartlarında Performans (Tear Sheet) ve Monte Carlo Analiz Raporları Üretir."""

    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital

    def _calculate_metrics(self, df: pd.DataFrame) -> dict:
        """Kapanmış işlemlerden Quant (Sayısal) Metrikler çıkarır."""
        if df.empty:
            return {"Total Trades": 0, "Win Rate": "0.00%", "Profit Factor": "0.00", "Net PnL": "$0.00", "Max Drawdown": "0.00%", "Risk of Ruin": "0.00%"}

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        total_trades = len(df)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        gross_profit = wins['pnl'].sum() if not wins.empty else 0.0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1.0 # 0 division koruması

        profit_factor = gross_profit / gross_loss
        net_pnl = df['pnl'].sum()

        # Drawdown Hesaplaması
        df['cumulative_pnl'] = df['pnl'].cumsum()
        df['equity_curve'] = self.initial_capital + df['cumulative_pnl']
        df['peak'] = df['equity_curve'].cummax()
        df['drawdown'] = (df['equity_curve'] - df['peak']) / df['peak']
        max_drawdown = abs(df['drawdown'].min())

        # Monte Carlo Risk of Ruin (%50 Kasa Erimişse İflas Sayılır)
        risk_of_ruin, mc_max_dd_99 = self._monte_carlo_simulation(df['pnl'].values)

        return {
            "Total Trades": total_trades,
            "Win Rate": f"{win_rate * 100:.2f}%",
            "Profit Factor": f"{profit_factor:.2f}",
            "Net PnL": f"${net_pnl:.2f}",
            "Max Drawdown": f"{max_drawdown * 100:.2f}%",
            "MC 99% Max DD": f"{mc_max_dd_99 * 100:.2f}%",
            "Risk of Ruin": f"{risk_of_ruin * 100:.2f}%"
        }

    def _monte_carlo_simulation(self, pnl_array: np.ndarray, simulations: int = 10000) -> tuple:
        """
        Geçmiş PNL değerlerini rastgele karıştırarak 10.000 paralel evren simüle eder.
        Döndürür: İflas Riski (%), %99 Güven Aralığında Beklenen Maksimum Drawdown (%)
        """
        if len(pnl_array) < 10:
            return 0.0, 0.0 # Yetersiz veri

        ruin_count = 0
        max_drawdowns = []

        # Hızlı Vektörel Simülasyon
        # 10.000 satır (simülasyon), N sütun (işlem sayısı) büyüklüğünde rastgele matrix
        n_trades = len(pnl_array)
        mc_matrix = np.random.choice(pnl_array, size=(simulations, n_trades), replace=True)

        # Kümülatif PnL Eğrisi
        cum_pnl = np.cumsum(mc_matrix, axis=1)
        equity_curves = self.initial_capital + cum_pnl

        # Maksimum Düşüş Hesaplama
        peaks = np.maximum.accumulate(equity_curves, axis=1)
        drawdowns = (equity_curves - peaks) / peaks
        max_drawdowns = np.abs(np.min(drawdowns, axis=1))

        # İflas (Ruin): Kasa başlangıç parasının %50'sinin altına düştü mü?
        ruined_simulations = np.any(equity_curves < (self.initial_capital * 0.5), axis=1)
        risk_of_ruin = np.sum(ruined_simulations) / simulations

        # %99 Confidence Interval Max Drawdown
        mc_max_dd_99 = np.percentile(max_drawdowns, 99)

        return risk_of_ruin, mc_max_dd_99

    def _generate_equity_plot(self, df: pd.DataFrame) -> str:
        """Kasa büyüme eğrisini Matplotlib ile çizer ve Base64 resim olarak döndürür."""
        if df.empty:
            return ""

        plt.figure(figsize=(10, 5))
        plt.plot(df['exit_time'], df['equity_curve'], label='Portföy Değeri', color='blue', linewidth=2)
        plt.fill_between(df['exit_time'], df['equity_curve'], df['peak'], color='red', alpha=0.3, label='Drawdown')
        plt.title('Kümülatif Getiri (Equity Curve)')
        plt.xlabel('Zaman')
        plt.ylabel('Bakiye (USD)')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.6)

        # Tarih eksenini okunabilir yap
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Hafızaya kaydet
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

        return plot_url

    def generate_tear_sheet(self) -> str:
        """Kapanmış işlemlerden ED Capital Standartlarında HTML Rapor (Tear Sheet) Üretir."""
        query = "SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time ASC"
        df = fetch_dataframe(query)

        metrics = self._calculate_metrics(df)
        plot_base64 = self._generate_equity_plot(df)

        # Kurumsal Şablon: Ana Başlık "Piyasalara Genel Bakış" (Yönetici Özeti yasak)
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #333; }
                h1 { color: #1a365d; border-bottom: 2px solid #1a365d; padding-bottom: 10px; }
                h2 { color: #2d3748; }
                .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 40px; }
                .metric-card { background: #f7fafc; padding: 20px; border-radius: 8px; border-left: 4px solid #3182ce; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .metric-title { font-size: 14px; color: #718096; text-transform: uppercase; letter-spacing: 1px; }
                .metric-value { font-size: 24px; font-weight: bold; color: #2b6cb0; margin-top: 10px; }
                img { max-width: 100%; height: auto; border: 1px solid #e2e8f0; border-radius: 8px; }
                .footer { margin-top: 50px; font-size: 12px; color: #a0aec0; text-align: center; border-top: 1px solid #e2e8f0; padding-top: 20px; }
            </style>
        </head>
        <body>
            <h1>ED Capital Quant Engine</h1>
            <h2>Piyasalara Genel Bakış</h2>
            <p>Otonom Sistem Performans Özeti - <i>Tarih: {{ date }}</i></p>

            <div class="metric-grid">
                <div class="metric-card"><div class="metric-title">Net PnL</div><div class="metric-value">{{ metrics['Net PnL'] }}</div></div>
                <div class="metric-card"><div class="metric-title">Win Rate</div><div class="metric-value">{{ metrics['Win Rate'] }}</div></div>
                <div class="metric-card"><div class="metric-title">Profit Factor</div><div class="metric-value">{{ metrics['Profit Factor'] }}</div></div>
                <div class="metric-card"><div class="metric-title">Total Trades</div><div class="metric-value">{{ metrics['Total Trades'] }}</div></div>
                <div class="metric-card"><div class="metric-title">Max Drawdown</div><div class="metric-value">{{ metrics['Max Drawdown'] }}</div></div>
                <div class="metric-card"><div class="metric-title">Risk of Ruin (MC)</div><div class="metric-value">{{ metrics['Risk of Ruin'] }}</div></div>
            </div>

            <h2>Kümülatif Getiri Eğrisi</h2>
            {% if plot %}
            <img src="data:image/png;base64,{{ plot }}" alt="Equity Curve">
            {% else %}
            <p><i>Yeterli işlem verisi bulunmamaktadır.</i></p>
            {% endif %}

            <div class="footer">
                Gizli ve Kişiye Özeldir. Geçmiş performans gelecekteki sonuçların garantisi değildir.
            </div>
        </body>
        </html>
        """

        # Jinja2 ile HTML Oluştur
        template = Environment(loader=FileSystemLoader(searchpath=".")).from_string(html_template)
        html_content = template.render(
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            metrics=metrics,
            plot=plot_base64
        )

        # Raporu HTML Olarak Kaydet
        report_path = os.path.join(REPORTS_DIR, f"tear_sheet_{datetime.now().strftime('%Y%m%d')}.html")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet Raporu Oluşturuldu: {report_path}")
        return report_path