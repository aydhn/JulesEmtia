import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from config import MAX_OPEN_POSITIONS, MAX_TOTAL_OPEN_RISK_PCT, CORRELATION_THRESHOLD
from logger import log
import paper_db as db

class PortfolioManager:
    def __init__(self, data_loader):
        self.data_loader = data_loader

    def check_global_limits(self, account_balance: float) -> bool:
        """Checks if we have room for new positions based on MAX_OPEN_POSITIONS and Total Risk."""
        open_trades = db.get_open_trades()
        num_open = len(open_trades)

        if num_open >= MAX_OPEN_POSITIONS:
            log.warning(f"Portfolio Limit Reached: {num_open}/{MAX_OPEN_POSITIONS} positions open.")
            return False

        # Optional: Calculate total open risk % here based on entry and sl
        return True

    def calculate_correlation(self, ticker1: str, ticker2: str, days: int = 30) -> float:
        """Calculates Pearson correlation between two tickers over the last N days."""
        try:
            # We need daily data for correlation
            df1 = self.data_loader.get_mtf_data(ticker1, period_htf=f"{days+10}d")['HTF']
            df2 = self.data_loader.get_mtf_data(ticker2, period_htf=f"{days+10}d")['HTF']

            if df1.empty or df2.empty:
                return 0.0

            # Align indices
            df1_close = df1['Close'].rename(ticker1)
            df2_close = df2['Close'].rename(ticker2)

            combined = pd.concat([df1_close, df2_close], axis=1).dropna()
            if len(combined) < 10:
                return 0.0

            # Calculate daily returns correlation
            returns = combined.pct_change().dropna()
            corr = returns[ticker1].corr(returns[ticker2])
            return corr
        except Exception as e:
            log.error(f"Correlation calc error: {e}")
            return 0.0

    def check_correlation_veto(self, new_ticker: str, new_direction: str) -> bool:
        """
        Vetos the trade if it's highly correlated (>0.75) with an existing open position
        in the SAME direction.
        Returns True if VETOED, False if APPROVED.
        """
        open_trades = db.get_open_trades()
        for trade in open_trades:
            existing_ticker = trade['ticker']
            existing_direction = trade['direction']

            corr = self.calculate_correlation(new_ticker, existing_ticker)

            # If highly correlated and same direction -> Duplicate Risk -> Veto
            if corr > CORRELATION_THRESHOLD and new_direction == existing_direction:
                log.warning(f"CORRELATION VETO: {new_ticker} is highly correlated ({corr:.2f}) with open {existing_ticker}.")
                return True

            # If highly negatively correlated and opposite direction -> Duplicate Risk -> Veto
            if corr < -CORRELATION_THRESHOLD and new_direction != existing_direction:
                log.warning(f"CORRELATION VETO: {new_ticker} is negatively correlated ({corr:.2f}) with open {existing_ticker} (Opposite dir).")
                return True

        return False

    def calculate_kelly_position_size(self, balance: float, win_rate: float, win_loss_ratio: float, entry_price: float, sl_price: float) -> float:
        """
        Calculates position size using the Fractional Kelly Criterion.
        f* = (bp - q) / b
        Where b = win_loss_ratio, p = win_rate, q = 1 - win_rate
        """
        # Fallback if no history
        if win_rate == 0 or win_loss_ratio == 0:
            kelly_pct = 0.01 # 1% fallback
        else:
            p = win_rate
            q = 1.0 - p
            b = win_loss_ratio

            full_kelly = (b * p - q) / b

            # Half-Kelly for safety
            half_kelly = full_kelly / 2.0

            # Cap at 4% max risk, Floor at 0.5%
            kelly_pct = max(0.005, min(0.04, half_kelly))

        risk_amount = balance * kelly_pct

        # Calculate size based on distance to stop loss
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            return 0.0

        size = risk_amount / sl_distance
        return size
