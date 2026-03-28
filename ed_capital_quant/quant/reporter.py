import pandas as pd
import matplotlib.pyplot as plt
from core.paper_db import PaperDB
import os
from quant.monte_carlo import MonteCarloSimulator

class Reporter:
    def __init__(self, db: PaperDB):
        self.db = db
        os.makedirs("reports", exist_ok=True)

    def generate_tear_sheet(self):
        df = pd.read_sql("SELECT * FROM trades WHERE status='Closed'", self.db.conn)
        if df.empty:
            return "reports/tear_sheet.md"

        win_rate = len(df[df['pnl'] > 0]) / len(df)
        total_pnl = df['pnl'].sum()
        gross_profit = df[df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Run Monte Carlo Stress Test
        trades_pnl = df['pnl'].tolist()
        mc_results = MonteCarloSimulator.run_simulation(trades_pnl)

        # Equity curve
        df['cumulative_pnl'] = df['pnl'].cumsum() + 10000.0  # Initial capital

        plt.figure(figsize=(10, 5))
        plt.plot(df['exit_time'], df['cumulative_pnl'], label="Kasa Büyüme Eğrisi", color="blue")
        plt.title("Piyasalara Genel Bakış - ED Capital")
        plt.xlabel("Zaman")
        plt.ylabel("Bakiye ($)")
        plt.legend()
        plt.grid()
        plt.savefig("reports/equity_curve.png")
        plt.close()

        report = f"""
        # Piyasalara Genel Bakış (ED Capital Kurumsal)

        ## Yönetici Özeti
        - Toplam PNL: {total_pnl:.2f}
        - Win Rate: %{win_rate*100:.2f}
        - Profit Factor: {profit_factor:.2f}
        - Toplam İşlem: {len(df)}

        ## Risk ve Monte Carlo Analizi
        - %99 Güven Aralığında Maksimum Düşüş: %{mc_results['max_dd_99']*100:.2f}
        - İflas Riski (Risk of Ruin): %{mc_results['risk_of_ruin']*100:.2f}
        """

        with open("reports/tear_sheet.md", "w") as f:
            f.write(report)

        return "reports/tear_sheet.md"
