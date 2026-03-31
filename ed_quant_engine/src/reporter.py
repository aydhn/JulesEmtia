import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from src.paper_db import db
from src.logger import logger
from src.notifier import send_telegram_message
from src.monte_carlo import MonteCarloSimulator
import os
import io

class TearSheetReporter:
    def __init__(self):
        self.report_dir = "reports/"
        os.makedirs(self.report_dir, exist_ok=True)
        self.monte_carlo = MonteCarloSimulator(simulations=1000) # Reduced for quick reporting

    def _get_closed_trades(self) -> pd.DataFrame:
        query = "SELECT * FROM trades WHERE status = 'Closed' AND pnl IS NOT NULL"
        df = pd.read_sql_query(query, db.conn)
        if not df.empty:
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            df.set_index('exit_time', inplace=True)
            df.sort_index(inplace=True)
        return df

    def generate_report(self) -> str:
        """
        Generates ED Capital standard Tear Sheet.
        Uses matplotlib to create an image, then sends it via Telegram.
        """
        df = self._get_closed_trades()
        if df.empty:
            logger.warning("No closed trades to report on.")
            return "Raporlanacak işlem yok."

        # Metrics Calculation
        total_trades = len(df)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0

        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = losses['pnl'].mean() if not losses.empty else 0

        # Cumulative PnL Curve
        df['cumulative_pnl'] = (1 + df['pnl']).cumprod() - 1

        # Drawdown calculation
        rolling_max = (1 + df['pnl']).cumprod().cummax()
        drawdown = ((1 + df['pnl']).cumprod() - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # Monte Carlo Risk Metrics
        mc_results = self.monte_carlo.run_simulation()
        mdd_99 = mc_results.get("Expected Max Drawdown (99% CI)", 0)
        risk_of_ruin = mc_results.get("Risk of Ruin (MDD > 50%)", 0)

        # Visualization
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(df.index, df['cumulative_pnl'] * 100, color='gold', linewidth=2)
        ax.set_title("ED Capital - Piyasalara Genel Bakış\nKümülatif Net Getiri (%)", color='white', pad=20)
        ax.set_ylabel("Getiri (%)")
        ax.grid(True, alpha=0.3, color='gray')

        # Add Metrics Text Box
        metrics_text = (
            f"Toplam İşlem: {total_trades}\n"
            f"İsabet Oranı: {win_rate*100:.1f}%\n"
            f"Kâr Faktörü: {profit_factor:.2f}\n"
            f"Max Drawdown: {max_drawdown*100:.1f}%\n"
            f"Ortalama Kâr: {avg_win*100:.2f}%\n"
            f"Ortalama Zarar: {avg_loss*100:.2f}%\n"
            f"-- Risk Metrikleri --\n"
            f"MC 99% CI Drawdown: {mdd_99*100:.1f}%\n"
            f"İflas Riski (Ruin): {risk_of_ruin*100:.2f}%"
        )
        props = dict(boxstyle='round', facecolor='black', alpha=0.8, edgecolor='gold')
        ax.text(0.05, 0.95, metrics_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=props, color='white')

        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
        buf.seek(0)
        plt.close(fig)

        # Send via Telegram
        self._send_photo_telegram(buf)
        return "Tear Sheet generated and sent."

    def _send_photo_telegram(self, photo_buffer: io.BytesIO):
        from src.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
        import requests

        if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID: return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': ('tearsheet.png', photo_buffer, 'image/png')}
        data = {'chat_id': ADMIN_CHAT_ID}

        try:
            requests.post(url, files=files, data=data, timeout=20)
            logger.info("Tear Sheet sent to Telegram.")
        except Exception as e:
            logger.error(f"Failed to send Tear Sheet photo: {e}")

