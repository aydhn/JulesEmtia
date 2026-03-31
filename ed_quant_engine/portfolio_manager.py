import pandas as pd
import numpy as np
from typing import List, Dict, Any
from paper_db import get_open_positions
from logger import setup_logger

logger = setup_logger("PortfolioManager")

def calculate_correlation_matrix(prices_dict: Dict[str, pd.Series], window: int = 60) -> pd.DataFrame:
    """Calculates rolling Pearson correlation matrix for dynamic risk exposure limits."""
    df = pd.DataFrame(prices_dict).pct_change().rolling(window=window).corr()
    return df.iloc[-len(prices_dict):] # Return just the latest matrix slice

def check_correlation_veto(ticker: str, direction: str, current_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
    """Blocks a signal if we already hold a position in a highly correlated asset in the same direction."""
    open_positions = get_open_positions()
    if not open_positions:
        return False # No veto needed if we have no positions

    try:
        corrs = current_matrix.loc[ticker]
        for pos in open_positions:
            pos_ticker = pos['ticker']
            pos_direction = pos['direction']

            if pos_ticker == ticker:
                continue

            corr_value = corrs.get(pos_ticker, 0.0)

            # High positive correlation + Same Direction = Double Exposure (Risk Duplication)
            if corr_value > threshold and direction == pos_direction:
                logger.warning(f"Korelasyon Vetosu: {ticker} ({direction}) reddedildi! {pos_ticker} ({pos_direction}) ile {corr_value:.2f} korelasyona sahip.")
                return True # VETO

            # High negative correlation + Opposite Direction = Double Exposure
            elif corr_value < -threshold and direction != pos_direction:
                logger.warning(f"Ters Korelasyon Vetosu: {ticker} ({direction}) reddedildi! {pos_ticker} ({pos_direction}) ile {corr_value:.2f} ters korelasyona sahip.")
                return True # VETO

        return False # All clear
    except Exception as e:
        logger.error(f"Korelasyon veto hatası: {str(e)}")
        return False

def check_global_exposure(max_positions: int = 3) -> bool:
    """Ensures we don't over-commit our capital. Blocks signal if portfolio is full."""
    open_count = len(get_open_positions())
    if open_count >= max_positions:
        logger.warning(f"Kapasite Dolu: {open_count}/{max_positions} pozisyon açık. Yeni sinyal reddedildi.")
        return True # VETO
    return False

def calculate_kelly_position_size(ticker: str, entry: float, stop_loss: float, balance: float, win_rate: float, avg_win: float, avg_loss: float, cap_pct: float = 0.04) -> float:
    """Calculates position size using the Kelly Criterion, bounded by a Fractional Safety Net and absolute hard cap."""
    if avg_loss == 0 or win_rate == 0:
        return balance * 0.01 / abs(entry - stop_loss) # Fallback to flat 1% risk if no history

    loss_rate = 1.0 - win_rate
    profit_factor = abs(avg_win / avg_loss)

    # Basic Kelly Formula: f = (bp - q) / b
    kelly_fraction = ((profit_factor * win_rate) - loss_rate) / profit_factor

    if kelly_fraction <= 0:
        logger.warning(f"Negatif Kelly ({kelly_fraction:.2f}) - Strateji avantajını kaybetmiş. İşlem reddedilmeli veya asgari risk uygulanmalı.")
        # We enforce a tiny fixed risk just to keep gathering data, or we could return 0 to veto completely.
        kelly_fraction = 0.005 # 0.5% fallback

    # JP Morgan Safety Buffer: Half-Kelly or Quarter-Kelly (from .env, usually 0.5)
    import os
    fraction_multiplier = float(os.getenv("KELLY_FRACTION", "0.5"))
    adjusted_kelly = kelly_fraction * fraction_multiplier

    # Hard Cap Protection (e.g., max 4% of bankroll per trade)
    final_risk_pct = min(adjusted_kelly, cap_pct)

    risk_amount = balance * final_risk_pct
    stop_distance = abs(entry - stop_loss)

    if stop_distance == 0:
        return 0

    lot_size = risk_amount / stop_distance
    logger.info(f"Kelly Optimizasyonu: WR %{win_rate*100:.1f}, B: {profit_factor:.2f} -> Önerilen Risk: %{final_risk_pct*100:.2f} (Sermaye: {balance:.2f}) -> {lot_size:.4f} Birim.")

    return lot_size
