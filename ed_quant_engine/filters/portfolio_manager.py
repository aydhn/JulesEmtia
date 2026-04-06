import pandas as pd
import numpy as np
from typing import Dict
from paper_db import get_open_positions
from logger import setup_logger

logger = setup_logger("PortfolioManager")

def calculate_correlation_matrix(prices_dict: Dict[str, pd.Series]) -> pd.DataFrame:
    """Phase 11: Calculates a rolling Pearson Correlation Matrix for the universe."""
    df = pd.DataFrame(prices_dict)
    # Ensure all series have the same length
    df.dropna(inplace=True)
    return df.corr(method='pearson')

def check_correlation_veto(new_ticker: str, direction: str, corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
    """
    Vetoes a signal if an existing open position is highly correlated and in the same direction.
    """
    if new_ticker not in corr_matrix.columns:
        return False

    open_positions = get_open_positions()
    for pos in open_positions:
        open_ticker = pos['ticker']
        open_direction = pos['direction']

        if open_ticker in corr_matrix.columns:
            corr_value = corr_matrix.loc[new_ticker, open_ticker]
            if corr_value > threshold and direction == open_direction:
                logger.warning(f"Korelasyon Vetosu: {new_ticker} ({direction}), {open_ticker} ile çok benzer (Korelasyon: {corr_value:.2f}). Riski katlamamak için reddedildi.")
                return True
            # Inverse correlation check (e.g. going Long on X and Long on strongly negative correlated Y)
            elif corr_value < -threshold and direction != open_direction:
                logger.warning(f"Ters Korelasyon Vetosu: {new_ticker} ({direction}), {open_ticker} ({open_direction}) ile zıt (Korelasyon: {corr_value:.2f}).")
                return True

    return False

def check_global_exposure(max_positions: int = 3, max_exposure_pct: float = 0.06) -> bool:
    """Checks if the portfolio has reached its maximum global limits."""
    open_positions = get_open_positions()
    if len(open_positions) >= max_positions:
        logger.warning(f"Global Limit Dolu: Maksimum pozisyon sayısına ({max_positions}) ulaşıldı.")
        return True
    return False

def calculate_kelly_position_size(ticker: str, entry: float, stop_loss: float, balance: float, win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Phase 15: Uses Fractional Kelly Criterion to size the position.
    Formulas:
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    kelly = (bp - q) / b
    fractional = kelly / 2
    """
    if avg_loss == 0: avg_loss = 1.0 # Prevent division by zero

    b = avg_win / avg_loss
    p = win_rate
    q = 1.0 - p

    if b <= 0: return 0.0

    kelly_pct = (b * p - q) / b

    # Safety Check: If Kelly is negative, strategy has no edge
    if kelly_pct <= 0:
        logger.warning(f"Kelly Kriteri Negatif: Bu varlıkta istatistiksel üstünlük yok. Sinyal reddedildi.")
        return 0.0

    # JP Morgan Risk Profile: Fractional Kelly (Half Kelly)
    fractional_kelly = kelly_pct / 2.0

    # Hard Cap
    max_risk_cap = 0.04 # Max 4% of total balance per trade
    final_risk_pct = min(fractional_kelly, max_risk_cap)

    risk_amount = balance * final_risk_pct
    distance_to_sl = abs(entry - stop_loss)

    if distance_to_sl == 0: return 0.0

    lot_size = risk_amount / distance_to_sl
    logger.info(f"Kelly Hesaplaması [{ticker}]: Risk= %{final_risk_pct*100:.2f} (${risk_amount:.2f}), Lot={lot_size:.4f}")

    return lot_size
