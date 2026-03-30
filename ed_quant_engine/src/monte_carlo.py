import numpy as np
import pandas as pd
from typing import Dict, List
from .logger import log_info, log_error

def run_monte_carlo(trades: List[Dict], initial_balance: float = 10000, n_simulations: int = 10000) -> dict:
    """
    Monte Carlo Risk of Ruin & Stress Testing (Hızlı Numpy/Vektörel Motor).
    Oluşmuş geçmiş işlemlerin rastgele sıralarla (replacement) binlerce kez simüle edilmesiyle
    Kasanın İflas Riski (Risk of Ruin) ve Beklenen Maksimum Düşüşü (Drawdown) hesaplar.
    """
    if not trades or len(trades) < 20:
        log_error("Monte Carlo için en az 20 kapalı işlem gereklidir.")
        return {}

    pnl_pcts = np.array([trade.get('pnl_pct', trade.get('PnL_Pct', 0.0)) for trade in trades]) / 100.0

    n_trades = len(pnl_pcts)

    # 1. Matris Oluşturma (10,000 simülasyon, n_trades satır)
    # Numpy'ın ultra-hızlı rastgele seçim fonksiyonu (replace=True)
    random_trades = np.random.choice(pnl_pcts, size=(n_simulations, n_trades), replace=True)

    # 2. Kümülatif Getiri (Compounding)
    # (1 + PnL_Pct) matrisini oluşturup kümülatif çarpıyoruz.
    growth_matrix = np.cumprod(1 + random_trades, axis=1) * initial_balance

    # 3. İflas Riski (Risk of Ruin) - Kasa yarıya düşerse (veya sıfıra)
    # Herhangi bir anda balance < initial_balance * 0.50 olanları bul
    ruin_threshold = initial_balance * 0.50
    ruined_simulations = np.any(growth_matrix < ruin_threshold, axis=1)
    risk_of_ruin_pct = np.mean(ruined_simulations) * 100

    # 4. Maksimum Düşüş (Max Drawdown)
    # Zirveden dibe düşüş (Peak to Trough)
    peaks = np.maximum.accumulate(growth_matrix, axis=1)
    drawdowns = (peaks - growth_matrix) / peaks
    max_drawdowns = np.max(drawdowns, axis=1) # Her simülasyon için 1 adet max_dd

    # 5. Güven Aralıkları (Confidence Intervals)
    # %95 ve %99 olasılıkla yaşanacak en kötü senaryo
    expected_mdd_95 = np.percentile(max_drawdowns, 95) * 100 # %95 güvenle Max DD
    expected_mdd_99 = np.percentile(max_drawdowns, 99) * 100 # %99 güvenle Max DD

    median_final_balance = np.median(growth_matrix[:, -1])

    log_info(f"🎲 MONTE CARLO BİTTİ ({n_simulations} Simülasyon). İflas Riski: %{risk_of_ruin_pct:.2f}")

    return {
        "Simulations": n_simulations,
        "RiskOfRuin_50Pct": risk_of_ruin_pct,
        "ExpectedMaxDrawdown_95CI": expected_mdd_95,
        "ExpectedMaxDrawdown_99CI": expected_mdd_99,
        "MedianFinalBalance": median_final_balance
    }
