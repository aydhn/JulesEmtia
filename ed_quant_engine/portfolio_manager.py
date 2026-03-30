import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from logger import log
from data_loader import UNIVERSE, _download_yf_data

# Threshold for correlation: +0.75 means highly correlated, -0.75 means highly inversely correlated
CORRELATION_THRESHOLD = 0.75

def calculate_correlation_matrix(period: str = "60d") -> pd.DataFrame:
    """
    Downloads historical close prices for the entire universe
    and returns a rolling Pearson Correlation Matrix.
    """
    try:
        prices_dict = {}
        for name, ticker in UNIVERSE.items():
            df = _download_yf_data(ticker, "1d", period)
            if not df.empty:
                prices_dict[ticker] = df['close']

        if not prices_dict:
            return pd.DataFrame()

        prices_df = pd.DataFrame(prices_dict)
        corr_matrix = prices_df.corr(method='pearson')
        return corr_matrix

    except Exception as e:
        log.error(f"Failed to calculate correlation matrix: {e}")
        return pd.DataFrame()


def is_correlation_veto(new_ticker: str, new_direction: str, open_trades: List[Dict], corr_matrix: pd.DataFrame) -> bool:
    """
    Risk Duplication Filter: Prevents opening a new trade if we already have an open
    trade in a highly correlated asset in the same direction.
    """
    if corr_matrix.empty or new_ticker not in corr_matrix.columns:
        return False

    for trade in open_trades:
        existing_ticker = trade['ticker']
        existing_direction = trade['direction']

        if existing_ticker in corr_matrix.columns:
            correlation = corr_matrix.loc[new_ticker, existing_ticker]

            # If the assets move together (> 0.75) AND we're betting the same way -> Veto (Risk duplication)
            if correlation > CORRELATION_THRESHOLD and new_direction == existing_direction:
                log.warning(f"Correlation Veto: {new_ticker} ({new_direction}) is highly correlated ({correlation:.2f}) with open trade {existing_ticker} ({existing_direction}).")
                return True

            # If the assets move opposite (< -0.75) AND we're betting opposite ways -> Veto (Risk duplication)
            elif correlation < -CORRELATION_THRESHOLD and new_direction != existing_direction:
                log.warning(f"Inverse Correlation Veto: {new_ticker} ({new_direction}) is highly inverse correlated ({correlation:.2f}) with open trade {existing_ticker} ({existing_direction}).")
                return True

    return False


def check_global_limits(open_trades: List[Dict], max_positions: int, global_exposure_limit: float, current_capital: float) -> bool:
    """
    Ensures the portfolio does not exceed predefined risk limits.
    Returns True if limits are EXCEEDED, False if safe to proceed.
    """
    if len(open_trades) >= max_positions:
        log.warning(f"Global Limit Veto: Maximum positions reached ({max_positions}).")
        return True

    total_exposure = sum(trade['position_size'] * trade['entry_price'] for trade in open_trades)
    max_allowed_exposure = current_capital * global_exposure_limit

    if total_exposure >= max_allowed_exposure:
        log.warning(f"Global Limit Veto: Portfolio exposure ({total_exposure:.2f}) exceeds limit ({max_allowed_exposure:.2f}).")
        return True

    return False
