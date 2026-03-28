import numpy as np
import pandas as pd
from utils.logger import log

def run_monte_carlo(closed_trades: pd.DataFrame, simulations=10000, initial_capital=10000.0) -> dict:
    # Phase 22: Fast vectorized Monte Carlo Engine
    if closed_trades.empty:
        return {"Risk_of_Ruin": 0, "Expected_MDD_99": 0}

    # Extract pct returns of each trade relative to initial capital for simplicity
    # A more precise way would be to track equity sequentially, but vectorized is much faster
    pct_returns = (closed_trades['pnl'] / initial_capital).values

    if len(pct_returns) < 5:
        return {"Risk_of_Ruin": 0, "Expected_MDD_99": 0}

    log.info(f"Monte Carlo Stres Testi Başlatılıyor... ({simulations} simülasyon)")

    results_mdd = []
    ruined_count = 0

    # 10,000 alternative universes with replacement
    # Number of steps = number of actual trades we have
    num_trades = len(pct_returns)

    # Generate all random indices at once for massive speedup
    random_indices = np.random.randint(0, num_trades, size=(simulations, num_trades))

    # Extract the returns
    sampled_returns = pct_returns[random_indices]

    # Cumulative sum for simple compounding (linear equity growth approximation for small % trades)
    # Using cumsum since pct_returns are relative to static initial capital in this model
    cumulative_equity = np.cumsum(sampled_returns, axis=1)

    # Calculate Max Drawdowns for each simulation row
    # MDD = (peak - trough) / peak. Since equity is 1 + cumulative,
    equity_curves = 1.0 + cumulative_equity

    # Running maximums
    peaks = np.maximum.accumulate(equity_curves, axis=1)
    drawdowns = (peaks - equity_curves) / peaks

    max_drawdowns = np.max(drawdowns, axis=1)

    # Risk of ruin: how many simulations dropped below 50% equity?
    ruined = np.any(equity_curves < 0.50, axis=1)
    ruined_count = np.sum(ruined)

    risk_of_ruin = ruined_count / simulations
    mdd_99 = np.percentile(max_drawdowns, 99)

    if risk_of_ruin > 0.01:
        log.warning(f"Kritik İflas Riski! ({risk_of_ruin:.1%}). Kelly Çarpanını (Fractional) Düşürün.")

    return {
        "Risk_of_Ruin": risk_of_ruin,
        "Expected_MDD_99": mdd_99
    }
