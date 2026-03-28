import pandas as pd
import numpy as np
from src.core.logger import logger
from src.core.config import CORRELATION_THRESHOLD, MAX_OPEN_POSITIONS, MAX_TOTAL_RISK_PERCENT
from src.core.paper_db import get_closed_trades
from typing import Dict, List

class PortfolioManager:
    def __init__(self):
        self.correlation_matrix = pd.DataFrame()

    def calculate_correlation_matrix(self, price_data: Dict[str, pd.DataFrame], lookback: int = 30):
        """
        Builds a rolling Pearson Correlation Matrix of the universe.
        """
        closes = {}
        for ticker, df in price_data.items():
            if not df.empty and 'Close' in df.columns:
                closes[ticker] = df['Close'].tail(lookback)

        if closes:
            df_closes = pd.DataFrame(closes).dropna()
            self.correlation_matrix = df_closes.corr(method='pearson')
            logger.info("Correlation Matrix Updated.")

    def correlation_veto(self, new_ticker: str, new_direction: str, open_positions: List[dict]) -> bool:
        """
        Checks if the new trade highly correlates with an existing open trade.
        Returns False if safe, True if vetoed (too correlated).
        """
        if self.correlation_matrix.empty or new_ticker not in self.correlation_matrix.columns:
            return False # Safe if no data

        for pos in open_positions:
            open_ticker = pos['ticker']
            open_direction = pos['direction']

            if open_ticker in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[new_ticker, open_ticker]

                # If highly positively correlated AND same direction -> Veto Risk Duplication
                if corr >= CORRELATION_THRESHOLD and new_direction == open_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} {new_direction} matches {open_ticker} ({corr:.2f})")
                    return True

                # If highly negatively correlated AND opposite direction -> Veto Risk Duplication
                if corr <= -CORRELATION_THRESHOLD and new_direction != open_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} {new_direction} inversely matches {open_ticker} ({corr:.2f})")
                    return True

        return False # Safe

    def check_global_limits(self, open_positions: List[dict]) -> bool:
        """
        Returns True if limits are exceeded.
        """
        if len(open_positions) >= MAX_OPEN_POSITIONS:
            logger.warning(f"Global Limit Veto: Maximum positions reached ({MAX_OPEN_POSITIONS}).")
            return True
        return False

    def get_dynamic_kelly_fraction(self, lookback: int = 50) -> float:
        """
        Calculates Fractional Kelly Criterion based on recent closed trades.
        """
        try:
            closed_trades = get_closed_trades()

            # If not enough trades, return a safe default (e.g., 1%)
            if len(closed_trades) < 5:
                logger.info("Not enough closed trades for Kelly, defaulting to 1% risk.")
                return 0.01

            # Consider only the last N trades
            recent_trades = closed_trades[-lookback:]
            df = pd.DataFrame(recent_trades)

            if 'pnl' not in df.columns or df['pnl'].isnull().all():
                return 0.01

            wins = df[df['pnl'] > 0]['pnl']
            losses = df[df['pnl'] <= 0]['pnl']

            win_rate = len(wins) / len(df)
            avg_win = wins.mean() if len(wins) > 0 else 0
            avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

            if avg_loss == 0 or win_rate == 0:
                logger.warning("Invalid W/L parameters for Kelly, defaulting to 1%.")
                return 0.01

            # Win/Loss Ratio (b)
            b = avg_win / avg_loss
            p = win_rate
            q = 1 - p

            # Kelly Formula (f*)
            f_star = (b * p - q) / b

            # Half-Kelly for safety
            fractional_kelly = f_star / 2.0

            # Cap at MAX_TOTAL_RISK_PERCENT (e.g., 6%) per trade
            capped_kelly = max(0.005, min(fractional_kelly, MAX_TOTAL_RISK_PERCENT))

            logger.info(f"Dynamic Kelly: WR={win_rate:.2f}, AW={avg_win:.2f}, AL={avg_loss:.2f} -> f*={f_star:.3f} -> Capped Half-Kelly={capped_kelly:.3f}")
            return capped_kelly

        except Exception as e:
            logger.error(f"Error calculating dynamic Kelly: {e}")
            return 0.01
