import pandas as pd
import matplotlib.pyplot as plt
import pdfkit
from logger import logger
from paper_db import paper_db

class Reporter:
    def __init__(self):
        self.template_path = "report_template.html"

    def generate_tear_sheet(self):
        '''
        Phase 13: ED Capital Kurumsal Sablonlu Tear Sheet Uretimi
        '''
        trades = paper_db.get_recent_trades(limit=1000)
        if not trades:
            logger.info("No trades to report.")
            return None

        df = pd.DataFrame(trades)

        # Calculate metrics
        total_pnl = df['pnl'].sum()
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]
        win_rate = len(wins) / len(df) if len(df) > 0 else 0

        gross_profit = wins['pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['pnl'].sum()) if not losses.empty else 1
        profit_factor = gross_profit / gross_loss

        # Phase 13: "Piyasalara Genel Bakis" header
        html_content = f'''
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .header {{ background-color: #0d1b2a; color: white; padding: 20px; text-align: center; }}
                .metrics {{ display: flex; justify-content: space-around; margin-top: 20px; }}
                .metric-box {{ border: 1px solid #ccc; padding: 15px; text-align: center; width: 20%; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>ED Capital Quant Engine</h1>
                <h2>Piyasalara Genel Bakış</h2>
            </div>
            <div class="metrics">
                <div class="metric-box"><h3>Toplam PnL</h3><p>${total_pnl:.2f}</p></div>
                <div class="metric-box"><h3>Isabet Orani</h3><p>{win_rate:.2%}</p></div>
                <div class="metric-box"><h3>Kâr Faktörü</h3><p>{profit_factor:.2f}</p></div>
            </div>
            <!-- More detailed tables and embedded Matplotlib base64 images go here -->
        </body>
        </html>
        '''

        # Save HTML
        report_file = "ed_capital_tear_sheet.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"Tear Sheet generated: {report_file}")
        return report_file

reporter = Reporter()