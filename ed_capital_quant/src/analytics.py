import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import os
import logging
from typing import Dict, List, Tuple
from multiprocessing import Pool, cpu_count

from config import logger, STARTING_BALANCE

class Backtester:
    """Vectorized backtesting engine modeling slippage and commissions."""
    def __init__(self, initial_capital: float = STARTING_BALANCE):
        self.initial_capital = initial_capital

    def run_backtest(self, df: pd.DataFrame, ticker: str, slippage_pct: float = 0.001, commission_pct: float = 0.0005) -> pd.DataFrame:
        """Runs a vectorized backtest on a pre-processed DataFrame with signals."""
        if df.empty or 'signal' not in df.columns:
            return pd.DataFrame()

        # Simulate Entry, SL, TP (Assumes Strategy logic already populated these)
        df['pnl'] = 0.0
        df['net_pnl'] = 0.0
        df['trade_status'] = 'None'
        df['exit_price'] = 0.0
        df['exit_time'] = pd.NaT

        # Simplified for loop for demonstration, fully vectorized WFO needs more complex shift logic
        in_trade = False
        entry_price = 0.0
        position_size = 0.0
        direction = 0
        sl_price = 0.0
        tp_price = 0.0

        capital = self.initial_capital
        trades = []

        for i in range(len(df)):
            row = df.iloc[i]

            if not in_trade:
                if row['signal'] == 1:
                    # Enter Long
                    direction = 1
                    in_trade = True
                    entry_price = row['close'] * (1 + slippage_pct)
                    sl_price = entry_price - (1.5 * row['atr_14'])
                    tp_price = entry_price + (3.0 * row['atr_14'])

                    # Simplistic Kelly for backtest (fixed risk)
                    risk_amount = capital * 0.02
                    position_size = risk_amount / (entry_price - sl_price)

                    capital -= entry_price * position_size * commission_pct

                elif row['signal'] == -1:
                    # Enter Short
                    direction = -1
                    in_trade = True
                    entry_price = row['close'] * (1 - slippage_pct)
                    sl_price = entry_price + (1.5 * row['atr_14'])
                    tp_price = entry_price - (3.0 * row['atr_14'])

                    risk_amount = capital * 0.02
                    position_size = risk_amount / (sl_price - entry_price)

                    capital -= entry_price * position_size * commission_pct
            else:
                # Check for exit (SL or TP)
                exit_reason = None
                exit_p = 0.0

                if direction == 1:
                    if row['low'] <= sl_price:
                        exit_p = sl_price * (1 - slippage_pct)
                        exit_reason = 'SL'
                    elif row['high'] >= tp_price:
                        exit_p = tp_price * (1 - slippage_pct)
                        exit_reason = 'TP'
                elif direction == -1:
                    if row['high'] >= sl_price:
                        exit_p = sl_price * (1 + slippage_pct)
                        exit_reason = 'SL'
                    elif row['low'] <= tp_price:
                        exit_p = tp_price * (1 + slippage_pct)
                        exit_reason = 'TP'

                if exit_reason:
                    # Close trade
                    gross_pnl = (exit_p - entry_price) * position_size * direction
                    commission = exit_p * position_size * commission_pct
                    net_pnl = gross_pnl - commission

                    capital += net_pnl

                    trades.append({
                        'entry_time': df.index[i], # Approx
                        'exit_time': df.index[i],
                        'ticker': ticker,
                        'direction': 'Long' if direction == 1 else 'Short',
                        'entry_price': entry_price,
                        'exit_price': exit_p,
                        'pnl': gross_pnl,
                        'net_pnl': net_pnl,
                        'capital': capital
                    })

                    in_trade = False

        return pd.DataFrame(trades)

    def calculate_metrics(self, trades_df: pd.DataFrame) -> Dict[str, float]:
        """Calculates Quant performance metrics from a history of trades."""
        if trades_df.empty:
            return {"Win Rate": 0, "Profit Factor": 0, "Max Drawdown": 0, "Total PnL": 0}

        wins = trades_df[trades_df['net_pnl'] > 0]
        losses = trades_df[trades_df['net_pnl'] <= 0]

        win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0
        gross_profit = wins['net_pnl'].sum() if not wins.empty else 0
        gross_loss = abs(losses['net_pnl'].sum()) if not losses.empty else 0

        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        total_pnl = trades_df['net_pnl'].sum()

        # Max Drawdown Calculation
        cumulative_capital = STARTING_BALANCE + trades_df['net_pnl'].cumsum()
        running_max = cumulative_capital.cummax()
        drawdown = (cumulative_capital - running_max) / running_max
        max_drawdown = drawdown.min() * 100 if len(drawdown) > 0 else 0

        return {
            "Total Trades": len(trades_df),
            "Win Rate (%)": round(win_rate * 100, 2),
            "Profit Factor": round(profit_factor, 2),
            "Max Drawdown (%)": round(max_drawdown, 2),
            "Total PnL ($)": round(total_pnl, 2),
            "Avg Win ($)": round(wins['net_pnl'].mean(), 2) if not wins.empty else 0,
            "Avg Loss ($)": round(losses['net_pnl'].mean(), 2) if not losses.empty else 0
        }

class WalkForwardOptimizer:
    """CPU-friendly rolling window Walk-Forward Analysis to prevent overfitting."""
    def __init__(self, backtester: Backtester):
        self.backtester = backtester

    def run_wfo(self, df: pd.DataFrame, ticker: str, is_window: int = 252*2, oos_window: int = 252//2) -> pd.DataFrame:
        """
        Splits data into In-Sample (IS) and Out-Of-Sample (OOS) rolling windows.
        IS Window: 2 Years. OOS Window: 6 Months.
        """
        logger.info(f"Starting Walk-Forward Optimization for {ticker}...")
        results = []

        if len(df) < is_window + oos_window:
            logger.warning(f"Not enough data for WFO on {ticker}. Required: {is_window+oos_window}, Got: {len(df)}")
            return pd.DataFrame()

        num_windows = (len(df) - is_window) // oos_window

        for w in range(num_windows):
            start_is = w * oos_window
            end_is = start_is + is_window
            end_oos = end_is + oos_window

            is_df = df.iloc[start_is:end_is]
            oos_df = df.iloc[end_is:end_oos]

            # In a real WFO, we would optimize parameters here on `is_df`
            # For this MVP, we evaluate static strategy stability across windows
            is_trades = self.backtester.run_backtest(is_df, ticker)
            oos_trades = self.backtester.run_backtest(oos_df, ticker)

            is_metrics = self.backtester.calculate_metrics(is_trades)
            oos_metrics = self.backtester.calculate_metrics(oos_trades)

            # Calculate Walk-Forward Efficiency (Annualized OOS Return / Annualized IS Return)
            # Simplified: Ratio of total PnL scaled by window length
            is_pnl_annualized = is_metrics['Total PnL ($)'] / 2.0
            oos_pnl_annualized = oos_metrics['Total PnL ($)'] / 0.5

            wfe = 0.0
            if is_pnl_annualized > 0:
                wfe = oos_pnl_annualized / is_pnl_annualized

            results.append({
                'Window': f"W{w+1}",
                'IS_PnL': is_metrics['Total PnL ($)'],
                'OOS_PnL': oos_metrics['Total PnL ($)'],
                'IS_WinRate': is_metrics['Win Rate (%)'],
                'OOS_WinRate': oos_metrics['Win Rate (%)'],
                'WFE (%)': round(wfe * 100, 2),
                'Robust': wfe >= 0.50 # Overfit flag
            })

        return pd.DataFrame(results)

class MonteCarloSimulator:
    """Numpy-based rapid risk of ruin and confidence interval simulator."""

    @staticmethod
    def run_simulation(trades_df: pd.DataFrame, num_simulations: int = 10000) -> Dict[str, float]:
        """Resamples trade PnL percentages 10,000 times to calculate expected max drawdown."""
        logger.info(f"Running {num_simulations} Monte Carlo Risk Simulations...")
        if trades_df.empty or len(trades_df) < 30:
            logger.warning("Insufficient trades for reliable Monte Carlo simulation (Need > 30).")
            return {}

        # Convert PnL to percentage of starting capital to normalize
        # Assuming fixed initial capital for scaling simplicity
        pnl_pct = (trades_df['net_pnl'] / STARTING_BALANCE).values
        n_trades = len(pnl_pct)

        # Vectorized resampling with replacement
        # Shape: (num_simulations, n_trades)
        simulated_returns = np.random.choice(pnl_pct, size=(num_simulations, n_trades), replace=True)

        # Cumulative returns over time for each simulation
        cumulative_returns = np.cumsum(simulated_returns, axis=1) + 1.0 # Base 1.0

        # Calculate Running Max and Drawdowns
        running_max = np.maximum.accumulate(cumulative_returns, axis=1)
        drawdowns = (cumulative_returns - running_max) / running_max

        # Minimum value in each simulation (Max Drawdown per simulation)
        max_drawdowns = np.min(drawdowns, axis=1)

        # Confidence Intervals
        expected_mdd_95 = np.percentile(max_drawdowns, 5) # 5th percentile because MDD is negative
        expected_mdd_99 = np.percentile(max_drawdowns, 1)

        # Risk of Ruin (Probability of losing > 50% capital)
        ruin_events = np.sum(np.min(cumulative_returns, axis=1) < 0.50)
        risk_of_ruin = ruin_events / num_simulations

        return {
            "Expected MDD (95% CI)": round(expected_mdd_95 * 100, 2),
            "Expected MDD (99% CI)": round(expected_mdd_99 * 100, 2),
            "Risk of Ruin (%)": round(risk_of_ruin * 100, 2)
        }

class Reporter:
    """Generates ED Capital standard HTML Tear Sheets."""
    def __init__(self, db_manager):
        self.db = db_manager
        os.makedirs("reports", exist_ok=True)

    def generate_tear_sheet(self):
        """Creates a standalone HTML report with Matplotlib charts encoded as base64."""
        logger.info("Generating ED Capital Executive Tear Sheet...")

        # 1. Fetch Data
        trades_df = self.db.get_closed_trades()
        balance = self.db.get_balance()

        if trades_df.empty:
            logger.warning("No closed trades to generate report.")
            return None

        # Calculate Metrics
        bt = Backtester()
        metrics = bt.calculate_metrics(trades_df)

        # Run Monte Carlo
        mc_results = MonteCarloSimulator.run_simulation(trades_df)
        if mc_results:
            metrics.update(mc_results)

        # 2. Generate Equity Curve Chart
        import base64
        from io import BytesIO

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))

        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        trades_df = trades_df.sort_values('exit_time')
        trades_df['cumulative_pnl'] = STARTING_BALANCE + trades_df['net_pnl'].cumsum()

        ax.plot(trades_df['exit_time'], trades_df['cumulative_pnl'], color='#00ffcc', linewidth=2)
        ax.set_title('Portföy Büyüme Eğrisi', color='white')
        ax.set_ylabel('Bakiye ($)', color='white')
        ax.grid(True, alpha=0.2)

        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        buf.seek(0)
        equity_chart_b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)

        # 3. HTML Template (ED Capital Corporate Style)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>ED Capital Quant Engine - Performans Raporu</title>
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }}
                h1 {{ color: #ffffff; text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                h2 {{ color: #00ffcc; border-bottom: 1px solid #333; padding-bottom: 5px; }}
                .container {{ max-width: 900px; margin: auto; background: #1e1e1e; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
                th {{ background-color: #2a2a2a; color: #b0b0b0; }}
                .metric-value {{ font-weight: bold; color: #ffffff; }}
                .positive {{ color: #00ffcc; }}
                .negative {{ color: #ff4d4d; }}
                .chart-container {{ text-align: center; margin-top: 30px; padding: 10px; background: #000; border-radius: 8px; }}
                .footer {{ text-align: center; margin-top: 40px; font-size: 0.8em; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>ED Capital Piyasalara Genel Bakış</h1>
                <p style="text-align: right; color: #888;">Tarih: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

                <h2>1. Yönetici Özeti</h2>
                <table>
                    <tr><th>Metrik</th><th>Değer</th></tr>
                    <tr><td>Başlangıç Bakiyesi</td><td class="metric-value">${STARTING_BALANCE:,.2f}</td></tr>
                    <tr><td>Güncel Bakiye</td><td class="metric-value">${balance:,.2f}</td></tr>
                    <tr><td>Toplam Net Kâr/Zarar</td><td class="metric-value {'positive' if metrics['Total PnL ($)'] > 0 else 'negative'}">${metrics['Total PnL ($)']:,.2f}</td></tr>
                    <tr><td>Win Rate (İsabet Oranı)</td><td class="metric-value">{metrics['Win Rate (%)']}%</td></tr>
                    <tr><td>Profit Factor</td><td class="metric-value">{metrics['Profit Factor']}</td></tr>
                    <tr><td>Maksimum Düşüş (Max Drawdown)</td><td class="metric-value negative">{metrics['Max Drawdown (%)']}%</td></tr>
                </table>

                <h2>2. Monte Carlo Risk & Stres Testi (10,000 Simülasyon)</h2>
                <table>
                    <tr><th>Risk Metriği</th><th>Sonuç</th></tr>
                    <tr><td>Beklenen Max Drawdown (95% Güven Aralığı)</td><td class="metric-value negative">{metrics.get('Expected MDD (95% CI)', 'N/A')}%</td></tr>
                    <tr><td>Beklenen Max Drawdown (99% Güven Aralığı)</td><td class="metric-value negative">{metrics.get('Expected MDD (99% CI)', 'N/A')}%</td></tr>
                    <tr><td>İflas Riski (Sermayenin %50'sini kaybetme)</td><td class="metric-value {'negative' if metrics.get('Risk of Ruin (%)', 0) > 1 else 'positive'}">{metrics.get('Risk of Ruin (%)', 'N/A')}%</td></tr>
                </table>

                <h2>3. Portföy Büyüme Eğrisi</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{equity_chart_b64}" alt="Equity Curve" style="max-width: 100%;">
                </div>

                <div class="footer">
                    GİZLİDİR. Sadece ED Capital İç Kullanımı İçindir. Algoritmik işlemler yüksek risk içerir.
                </div>
            </div>
        </body>
        </html>
        """

        file_path = f"reports/TearSheet_{datetime.now().strftime('%Y%m%d')}.html"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"Report generated successfully: {file_path}")
        return file_path
