import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from paper_db import get_closed_trades
from logger import setup_logger
import os

logger = setup_logger("MonteCarlo")

def run_monte_carlo_simulation(n_simulations: int = 10000) -> dict:
    """Runs a Monte Carlo simulation (with replacement) on historical trade PnL percentages to assess Risk of Ruin."""
    df = get_closed_trades()
    if df.empty or len(df) < 50:
        logger.warning("Monte Carlo için yeterli kapalı işlem (min 50) bulunamadı.")
        return {}

    # Get sequence of returns (percentages)
    returns = df['pnl_percent'] / 100.0

    # We simulate starting with $1.0 and compounding
    simulated_equity_curves = np.zeros((n_simulations, len(returns)))

    # Fast Vectorized Approach
    for i in range(n_simulations):
        # Sample with replacement
        simulated_returns = np.random.choice(returns, size=len(returns), replace=True)
        # Calculate cumulative returns
        simulated_equity_curves[i] = np.cumprod(1 + simulated_returns)

    # Calculate Max Drawdowns for each simulation
    max_drawdowns = np.zeros(n_simulations)
    for i in range(n_simulations):
        curve = simulated_equity_curves[i]
        peaks = np.maximum.accumulate(curve)
        drawdowns = (curve - peaks) / peaks
        max_drawdowns[i] = np.min(drawdowns) # Negative values

    # Risk Metrics
    # Expected Max Drawdown at 95% and 99% Confidence Intervals
    # e.g., only 1% of simulations had a drawdown worse than X
    var_95 = np.percentile(max_drawdowns, 5) # 5th percentile of negative numbers
    var_99 = np.percentile(max_drawdowns, 1)

    # Risk of Ruin (Probability of hitting a 50% drawdown)
    ruin_threshold = -0.50
    ruin_count = np.sum(max_drawdowns <= ruin_threshold)
    risk_of_ruin_pct = (ruin_count / n_simulations) * 100

    logger.info(f"Monte Carlo ({n_simulations} simülasyon): %99 Güvenle Max Drawdown: {var_99*100:.2f}% | İflas Riski: %{risk_of_ruin_pct:.2f}")

    if risk_of_ruin_pct > 1.0:
        logger.critical(f"İFLAS RİSKİ YÜKSEK! Kasa büyüklüğü yönetimi (Kelly) agresif. (%{risk_of_ruin_pct:.2f})")

    # Generate Chart (Spaghetti Plot)
    plt.figure(figsize=(10, 5))
    # Plot a subset to avoid crashing matplotlib (e.g., 100 curves)
    subset_curves = simulated_equity_curves[:100]
    for curve in subset_curves:
        plt.plot(curve, color='blue', alpha=0.05)

    plt.plot(np.median(simulated_equity_curves, axis=0), color='red', linewidth=2, label='Medyan Beklenti')
    plt.title('Monte Carlo Simülasyonu (N=10,000)', fontsize=14)
    plt.ylabel('Sermaye Çarpanı')
    plt.xlabel('İşlem Sırası')
    plt.legend()

    chart_path = os.path.join("reports", "monte_carlo.png")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    return {
        "var_95": var_95 * 100,
        "var_99": var_99 * 100,
        "risk_of_ruin": risk_of_ruin_pct,
        "chart_path": chart_path
    }
