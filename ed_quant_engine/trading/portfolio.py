import pandas as pd
import numpy as np
from core.config import MAX_OPEN_POSITIONS, MAX_GLOBAL_EXPOSURE, KELLY_FRACTION
from core.logger import get_logger

log = get_logger()

def calculate_correlation(df_dict: dict, period=30) -> pd.DataFrame:
    # Create a unified dataframe of closing prices
    close_df = pd.DataFrame()
    for ticker, df in df_dict.items():
        if not df.empty and 'Close' in df.columns:
            close_df[ticker] = df['Close']

    if close_df.empty:
        return pd.DataFrame()

    return close_df.tail(period).corr()

def check_correlation_veto(new_ticker, new_direction, open_positions, corr_matrix, threshold=0.75):
    for pos in open_positions:
        open_ticker = pos['ticker']
        open_dir = pos['direction']

        if open_ticker in corr_matrix.columns and new_ticker in corr_matrix.columns:
            corr_val = corr_matrix.loc[new_ticker, open_ticker]
            if corr_val > threshold and new_direction == open_dir:
                log.warning(f"Correlation Veto: {new_ticker} vs {open_ticker} ({corr_val:.2f})")
                return True
            if corr_val < -threshold and new_direction != open_dir:
                log.warning(f"Inverse Correlation Veto: {new_ticker} vs {open_ticker} ({corr_val:.2f})")
                return True
    return False

def calculate_kelly_size(balance: float, atr: float, entry_price: float, win_rate: float, avg_win: float, avg_loss: float) -> float:
    if win_rate == 0 or avg_loss == 0:
        return 0.0

    b = avg_win / abs(avg_loss)
    p = win_rate
    q = 1 - p

    kelly_f = (b * p - q) / b

    # Fractional Kelly (Safety Buffer)
    fractional_kelly = kelly_f * KELLY_FRACTION

    # Hard Cap: Max 4% risk per trade
    fractional_kelly = min(max(fractional_kelly, 0.005), 0.04)

    if fractional_kelly <= 0:
        return 0.0

    risk_amount = balance * fractional_kelly

    # Calculate Lot Size: Risk Amount / Distance to Stop Loss
    lot_size = risk_amount / (1.5 * atr)

    return lot_size
