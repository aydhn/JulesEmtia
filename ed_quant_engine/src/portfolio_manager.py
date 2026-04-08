import pandas as pd
import numpy as np
import logging
from typing import Dict, List
from src.broker import BaseBroker

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Phase 11: Correlation Veto & Global Limits
    Phase 15: Fractional Kelly Sizing
    """
    def __init__(self, broker: BaseBroker, max_open_positions: int = 4, max_global_risk: float = 0.06):
        self.broker = broker
        self.max_open_positions = max_open_positions
        self.max_global_risk = max_global_risk
        self.corr_threshold = 0.75

    def calculate_kelly_fraction(self) -> float:
        """Calculates Half-Kelly based on closed trades."""
        if hasattr(self.broker, "db_path"):
            import sqlite3
            conn = sqlite3.connect(self.broker.db_path)
            df = pd.read_sql("SELECT pnl FROM trades WHERE status = 'Closed' ORDER BY trade_id DESC LIMIT 50", conn)
            conn.close()
        else:
            return 0.01 # Fallback

        if len(df) < 10:
            return 0.01

        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        if len(wins) == 0 or len(losses) == 0:
            return 0.01

        p = len(wins) / len(df)
        q = 1.0 - p

        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean())

        b = avg_win / avg_loss if avg_loss != 0 else 1.0
        if b == 0: return 0.01

        f_star = (b * p - q) / b
        half_kelly = f_star / 2.0

        # Hard Cap at 4%
        return max(0.005, min(half_kelly, 0.04))

    def calculate_correlation_matrix(self, price_data_dict: Dict[str, pd.DataFrame], window: int = 60) -> pd.DataFrame:
        """Calculate rolling Pearson correlation matrix for the universe."""
        prices = {}
        for ticker, df in price_data_dict.items():
            if not df.empty and 'Close' in df.columns:
                prices[ticker] = df['Close'].tail(window)

        if not prices:
            return pd.DataFrame()

        prices_df = pd.DataFrame(prices)
        return prices_df.corr(method='pearson')

    def check_correlation_veto(self, new_ticker: str, new_dir: str, corr_matrix: pd.DataFrame) -> bool:
        """Prevents doubling risk on highly correlated assets."""
        open_pos = self.broker.get_open_positions()
        if len(open_pos) >= self.max_open_positions:
            logger.warning(f"Global Limit Veto: Already {self.max_open_positions} open positions.")
            return True # Veto = True

        for pos in open_pos:
            existing_ticker = pos['ticker']
            existing_dir = pos['direction']

            if new_ticker == existing_ticker and new_dir == existing_dir:
                return True # Don't open same direction on same asset twice

            if new_ticker in corr_matrix.columns and existing_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, existing_ticker]
                if corr > self.corr_threshold and new_dir == existing_dir:
                    logger.warning(f"Correlation Veto! {new_ticker} is highly correlated ({corr:.2f}) with open position {existing_ticker}.")
                    return True # Veto = True

        return False # No Veto
