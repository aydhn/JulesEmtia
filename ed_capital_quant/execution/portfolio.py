import pandas as pd
import numpy as np
from core.paper_db import db
from core.config import MAX_GLOBAL_EXPOSURE
from data.data_loader import fetch_data_with_retry
from utils.logger import log

def calculate_correlation(tickers: list, period="60d") -> pd.DataFrame:
    dfs = []
    for ticker in tickers:
        df = fetch_data_with_retry(ticker, "1d", period=period)
        if not df.empty:
            dfs.append(df['Close'].rename(ticker))
    if dfs:
        df_combined = pd.concat(dfs, axis=1)
        return df_combined.corr(method='pearson')
    return pd.DataFrame()

def is_correlated(new_ticker: str, open_tickers: list, corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
    if new_ticker not in corr_matrix.columns:
        return False

    for ot in open_tickers:
        if ot in corr_matrix.columns:
            if abs(corr_matrix.loc[new_ticker, ot]) > threshold:
                log.info(f"VETO: {new_ticker} has > {threshold} correlation with open trade {ot}.")
                return True
    return False

def calculate_position_size(capital: float, entry_price: float, sl_price: float) -> float:
    # Phase 15: Half-Kelly Criterion implementation based on past N trades
    closed_trades = db.get_closed_trades()

    win_rate = 0.50
    b = 1.0 # Average Win / Average Loss

    if len(closed_trades) >= 20: # Wait for enough sample size
        wins = closed_trades[closed_trades['pnl'] > 0]
        losses = closed_trades[closed_trades['pnl'] < 0]

        if len(closed_trades) > 0:
            win_rate = len(wins) / len(closed_trades)

        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 0

        if avg_loss > 0:
            b = avg_win / avg_loss

    # f* = (bp - q) / b
    q = 1.0 - win_rate
    f_star = (b * win_rate - q) / b if b > 0 else 0

    # Half-Kelly safety buffer
    half_kelly = max(0.005, min(MAX_GLOBAL_EXPOSURE, f_star / 2.0))

    risk_amount = capital * half_kelly
    distance = abs(entry_price - sl_price)

    size = risk_amount / distance if distance > 0 else 0
    log.info(f"Kelly Fraction: {half_kelly:.2%} | Risking: ${risk_amount:.2f} | Lot Size: {size}")
    return size
