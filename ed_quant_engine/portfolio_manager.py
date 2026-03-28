import pandas as pd
import yfinance as yf
from typing import List, Tuple
from config import MAX_OPEN_POSITIONS, MAX_TOTAL_EXPOSURE_PCT
from logger import get_logger

log = get_logger()

def calculate_correlation_matrix(tickers: List[str], period: str = "60d") -> pd.DataFrame:
    """Calculates Rolling Pearson Correlation matrix to veto duplicate risk."""
    df_list = []
    for t in tickers:
        try:
            data = yf.download(t, period=period, interval="1d", progress=False)['Close']
            if isinstance(data, pd.DataFrame):
                data = data.iloc[:, 0]
            data.name = t
            df_list.append(data)
        except:
            pass

    if not df_list: return pd.DataFrame()

    prices = pd.concat(df_list, axis=1).ffill().dropna()
    returns = prices.pct_change().dropna()
    return returns.corr(method='pearson')

def check_correlation_veto(new_ticker: str, new_direction: str, open_trades: List[tuple], corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
    """
    Returns True if the signal should be VETOED (rejected).
    Prevents stacking Longs on Gold and Silver if correlation > 0.75.
    """
    if corr_matrix.empty or new_ticker not in corr_matrix.columns:
        return False

    for trade in open_trades:
        existing_ticker = trade[1]
        existing_dir = trade[2]

        if existing_ticker in corr_matrix.columns:
            corr_val = corr_matrix.loc[new_ticker, existing_ticker]

            # Same direction, high positive correlation = Duplicate Risk
            if corr_val > threshold and new_direction == existing_dir:
                log.warning(f"CORRELATION VETO: Rejecting {new_direction} {new_ticker} due to {corr_val:.2f} corr with existing {existing_ticker}.")
                return True

            # Opposite direction, high negative correlation = Hedge (Allow or Reject? We reject to avoid flat exposure)
            if corr_val < -threshold and new_direction != existing_dir:
                log.warning(f"CORRELATION VETO (Inverse): Rejecting {new_direction} {new_ticker} due to {corr_val:.2f} corr with existing {existing_ticker}.")
                return True

    return False

def check_global_limits(open_trades: List[tuple], account_balance: float) -> bool:
    """Returns True if the signal should be VETOED due to Global Exposure limits."""
    if len(open_trades) >= MAX_OPEN_POSITIONS:
        log.warning(f"EXPOSURE VETO: Max positions ({MAX_OPEN_POSITIONS}) reached.")
        return True

    total_risk_dollars = sum([abs((t[4] - t[5]) * t[7]) for t in open_trades]) # (Entry - SL) * Qty
    risk_pct = total_risk_dollars / account_balance

    if risk_pct >= MAX_TOTAL_EXPOSURE_PCT:
        log.warning(f"EXPOSURE VETO: Total risk ({risk_pct:.2%}) exceeds MAX ({MAX_TOTAL_EXPOSURE_PCT:.2%}).")
        return True

    return False
