import pandas as pd
import numpy as np
import os
from paper_db import get_closed_trades
from utils.logger import setup_logger

logger = setup_logger("MonteCarloEngine")

def run_monte_carlo_simulation(simulations: int = 10000) -> dict:
    """
    Phase 22: Fast vectorized Monte Carlo Risk Simulation.
    Calculates expected Max Drawdown at 99% CI and Risk of Ruin.
    """
    logger.info(f"Monte Carlo Simülasyonu başlatılıyor ({simulations} iterasyon)...")
    df = get_closed_trades()

    if df.empty or len(df) < 20:
        logger.warning("Monte Carlo için yeterli kapalı işlem yok (En az 20 gerekli).")
        return {}

    initial_balance = float(os.getenv("INITIAL_BALANCE", "10000.0"))

    # Extract percentage returns per trade
    returns = df['pnl_percent'].values / 100.0 # Convert 2.5 to 0.025
    n_trades = len(returns)

    # Vectorized random sampling with replacement
    # Shape: (simulations, n_trades)
    random_indices = np.random.randint(0, n_trades, size=(simulations, n_trades))
    simulated_returns = returns[random_indices]

    # Cumulative product to build equity curves
    # Add 1.0 to returns (e.g. 0.025 -> 1.025)
    equity_curves = initial_balance * np.cumprod(1 + simulated_returns, axis=1)

    # Calculate Drawdowns for all paths
    peak = np.maximum.accumulate(equity_curves, axis=1)
    drawdowns = (peak - equity_curves) / peak

    # Max drawdown per simulation
    max_drawdowns = np.max(drawdowns, axis=1)

    # Risk Metrics
    mdd_95 = np.percentile(max_drawdowns, 95)
    mdd_99 = np.percentile(max_drawdowns, 99)

    # Risk of Ruin: Probability of losing 50% of peak equity
    ruin_threshold = 0.50
    ruined_simulations = np.sum(max_drawdowns >= ruin_threshold)
    risk_of_ruin = (ruined_simulations / simulations) * 100.0

    logger.info(f"--- Monte Carlo Sonuçları ---")
    logger.info(f"%95 Güven Aralığında Max Drawdown: %{mdd_95*100:.2f}")
    logger.info(f"%99 Güven Aralığında Max Drawdown: %{mdd_99*100:.2f}")
    logger.info(f"İflas Riski (Risk of Ruin): %{risk_of_ruin:.2f}")

    if risk_of_ruin > 1.0:
        logger.warning("DİKKAT: İflas riski %1'in üzerinde! Agresif Kelly çarpanlarını küçültün.")

    return {
        "mdd_95": mdd_95,
        "mdd_99": mdd_99,
        "risk_of_ruin": risk_of_ruin
    }

if __name__ == "__main__":
    run_monte_carlo_simulation()
