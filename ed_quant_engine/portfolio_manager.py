import pandas as pd
import numpy as np
from typing import Dict, Any, List
from ed_quant_engine.logger import log
from ed_quant_engine.config import CORRELATION_THRESHOLD, MAX_OPEN_POSITIONS, GLOBAL_MAX_EXPOSURE
from ed_quant_engine.paper_db import get_open_trades

def calculate_correlation_matrix(universe_data: Dict[str, Dict[str, pd.DataFrame]], lookback: int = 60) -> pd.DataFrame:
    """Calculates a rolling Pearson correlation matrix of daily returns."""
    returns_dict = {}

    for ticker, dfs in universe_data.items():
        if '1d' in dfs and not dfs['1d'].empty:
            df = dfs['1d'].tail(lookback)
            if 'Close' in df.columns:
                returns_dict[ticker] = np.log(df['Close'] / df['Close'].shift(1))

    if not returns_dict:
        log.warning("No daily returns available for correlation matrix.")
        return pd.DataFrame()

    returns_df = pd.DataFrame(returns_dict).dropna()
    corr_matrix = returns_df.corr()
    log.debug(f"Correlation matrix calculated over {len(returns_df)} days.")
    return corr_matrix

def correlation_veto(new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame, open_trades: List[Dict[str, Any]]) -> bool:
    """Vetoes new trades if they are highly correlated with existing open trades in the same direction."""
    if corr_matrix.empty or new_ticker not in corr_matrix.columns:
        return False

    for trade in open_trades:
        existing_ticker = trade['ticker']
        existing_direction = trade['direction']

        if existing_ticker in corr_matrix.columns:
            corr_value = corr_matrix.loc[new_ticker, existing_ticker]

            # If highly positively correlated and same direction -> VETO (Risk Duplication)
            if corr_value >= CORRELATION_THRESHOLD and new_direction == existing_direction:
                log.info(f"Correlation Veto: {new_ticker} {new_direction} rejected. High correlation ({corr_value:.2f}) with open {existing_ticker} {existing_direction}")
                return True

            # If highly negatively correlated and opposite direction -> VETO (Hedge Risk Duplication)
            # Example: Long USD/TRY and Short EUR/TRY is basically the same bet against TRY.
            if corr_value <= -CORRELATION_THRESHOLD and new_direction != existing_direction:
                log.info(f"Correlation Veto: {new_ticker} {new_direction} rejected. High inverse correlation ({corr_value:.2f}) with open {existing_ticker} {existing_direction}")
                return True

    return False

def check_global_limits(open_trades: List[Dict[str, Any]], current_capital: float) -> bool:
    """Checks if maximum number of trades or total portfolio risk exposure is exceeded."""
    if len(open_trades) >= MAX_OPEN_POSITIONS:
        log.info(f"Global Limit Veto: Max open positions ({MAX_OPEN_POSITIONS}) reached.")
        return True

    total_exposure_pct = sum(t['position_size'] for t in open_trades) / 100.0
    if total_exposure_pct >= GLOBAL_MAX_EXPOSURE:
        log.info(f"Global Limit Veto: Portfolio exposure ({total_exposure_pct:.2%}) exceeds limit ({GLOBAL_MAX_EXPOSURE:.2%})")
        return True

    return False

def calculate_fractional_kelly(closed_trades: pd.DataFrame, fallback_risk: float = 0.02) -> float:
    """Calculates Half-Kelly optimal fraction for position sizing."""
    if closed_trades.empty or len(closed_trades) < 20: # Need history
        return fallback_risk

    wins = closed_trades[closed_trades['pnl'] > 0]
    losses = closed_trades[closed_trades['pnl'] <= 0]

    if wins.empty or losses.empty:
        return fallback_risk

    p = len(wins) / len(closed_trades) # Win rate
    q = 1.0 - p # Loss rate

    avg_win = wins['pnl'].mean()
    avg_loss = abs(losses['pnl'].mean())

    if avg_loss == 0: return fallback_risk

    b = avg_win / avg_loss # Win/Loss ratio

    f_star = (b * p - q) / b # Full Kelly fraction

    # Fractional Kelly (Half-Kelly)
    f_half = f_star / 2.0

    # Hard Cap Protection (Max 4% risk per trade)
    HARD_CAP = 0.04

    if f_half <= 0:
        log.warning(f"Kelly fraction <= 0 ({f_half:.4f}). Strategy losing edge. Reducing risk.")
        return 0.005 # Minimal risk

    f_final = min(f_half, HARD_CAP)
    log.debug(f"Fractional Kelly Calculated: {f_final:.2%}")
    return f_final
