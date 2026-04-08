import pandas as pd
import numpy as np
from src.config import MAX_POSITIONS, MAX_GLOBAL_RISK_PCT, CORRELATION_THRESHOLD
from src.logger import get_logger
import src.paper_db as db

logger = get_logger()

def check_global_limits(current_balance: float) -> bool:
    open_trades = db.get_open_trades()
    if len(open_trades) >= MAX_POSITIONS:
        logger.info(f"Global Limit Reached: Max {MAX_POSITIONS} positions active.")
        return False

    # Simplified exposure check
    # In a real scenario, calculate margin used.
    return True

def calculate_correlation_matrix(price_dict: dict) -> pd.DataFrame:
    """
    Calculates 30-day rolling correlation given a dict of {ticker: close_series}
    """
    df = pd.DataFrame(price_dict)
    if df.empty:
        return pd.DataFrame()
    return df.corr(method='pearson')

def check_correlation_veto(ticker: str, direction: str, corr_matrix: pd.DataFrame) -> bool:
    """
    Vetos the signal if highly correlated with an already open position in the same direction.
    """
    open_trades = db.get_open_trades()
    if not open_trades or corr_matrix.empty:
        return True # Approved

    for trade in open_trades:
        open_ticker = trade['ticker']
        open_dir = trade['direction']

        if ticker in corr_matrix.columns and open_ticker in corr_matrix.columns:
            corr = corr_matrix.loc[ticker, open_ticker]
            if abs(corr) > CORRELATION_THRESHOLD:
                if (corr > 0 and direction == open_dir) or (corr < 0 and direction != open_dir):
                    logger.info(f"Correlation Veto: {ticker} ({direction}) highly correlated ({corr:.2f}) with open trade {open_ticker} ({open_dir})")
                    return False
    return True # Approved

def calculate_fractional_kelly() -> float:
    """
    Calculates Half-Kelly based on historical closed trades.
    Formula: K = (bp - q) / b
    where p = win probability, q = 1-p, b = win/loss ratio.
    Returns the percentage of bankroll to risk.
    """
    df = db.get_closed_trades()
    if len(df) < 10:
        return 0.01 # Default 1% risk if not enough data

    winning_trades = df[df['pnl'] > 0]
    losing_trades = df[df['pnl'] <= 0]

    p = len(winning_trades) / len(df)
    q = 1 - p

    avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
    avg_loss = abs(losing_trades['pnl'].mean()) if len(losing_trades) > 0 else 0

    if avg_loss == 0 or avg_win == 0:
        return 0.01

    b = avg_win / avg_loss

    kelly = (b * p - q) / b

    # Fractional Kelly (Half)
    half_kelly = kelly / 2.0

    # Cap between 0.5% and MAX_SINGLE_RISK_CAP (4%)
    final_risk_pct = max(0.005, min(half_kelly, 0.04))
    return final_risk_pct
