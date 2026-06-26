from __future__ import annotations

import pandas as pd

from src.portfolio import (
    calculate_correlation_matrix,
    check_correlation_veto,
    check_global_limits,
    evaluate_signal_risk,
)


class PortfolioManager:
    """
    Backward-compatible facade over src.portfolio.
    New code should import src.portfolio directly.
    """

    def calculate_correlation_matrix(self, price_dict: dict[str, pd.Series]) -> pd.DataFrame:
        return calculate_correlation_matrix(price_dict)

    def check_correlation_veto(self, new_ticker: str, new_dir: str, corr_matrix: pd.DataFrame) -> bool:
        return not check_correlation_veto(new_ticker, new_dir, corr_matrix)

    def check_global_limits(self, current_balance: float) -> bool:
        return check_global_limits(current_balance)

    def evaluate_signal_risk(self, signal: dict, corr_matrix: pd.DataFrame, current_balance: float):
        return evaluate_signal_risk(signal, corr_matrix, current_balance)
