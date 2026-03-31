import pandas as pd
from typing import Dict, List
from src.logger import logger
from src.paper_db import db
from src.config import ALL_TICKERS

class PortfolioManager:
    def __init__(self, max_open_trades: int = 4, max_risk_exposure: float = 0.06):
        self.max_open_trades = max_open_trades
        self.max_risk_exposure = max_risk_exposure

    def calculate_correlation_matrix(self, data: Dict[str, pd.DataFrame], window: int = 30) -> pd.DataFrame:
        """
        Calculates a rolling Pearson correlation matrix for the past `window` days using 'Close' prices.
        """
        closes = pd.DataFrame({ticker: df['Close'] for ticker, df in data.items() if not df.empty})
        if closes.empty:
            return pd.DataFrame()

        corr_matrix = closes.tail(window).corr()
        return corr_matrix

    def veto_correlation(self, new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
        """
        Vetoes a trade if it's highly correlated with an existing open trade in the same direction.
        """
        if corr_matrix.empty or new_ticker not in corr_matrix.columns:
            return False

        open_trades = db.get_open_trades()
        for trade in open_trades:
            existing_ticker = trade['ticker']
            existing_direction = trade['direction']

            if existing_ticker in corr_matrix.columns:
                correlation = corr_matrix.loc[new_ticker, existing_ticker]

                # Risk Duplication Filter
                if correlation > threshold and new_direction == existing_direction:
                    logger.info(f"Correlation Veto: {new_ticker} ({new_direction}) is highly correlated ({correlation:.2f}) with open {existing_ticker} ({existing_direction}).")
                    return True

                # Counter-directional Hedge Risk (optional implementation)
                if correlation < -threshold and new_direction == existing_direction:
                     logger.info(f"Correlation Veto: {new_ticker} ({new_direction}) is highly negatively correlated ({correlation:.2f}) with open {existing_ticker} ({existing_direction}).")
                     return True
        return False

    def veto_global_limits(self, capital: float, current_risk_pct: float) -> bool:
        """
        Vetoes a trade if max open trades or global risk limits are reached.
        """
        open_trades = db.get_open_trades()

        if len(open_trades) >= self.max_open_trades:
            logger.info(f"Global Limit Veto: Max open trades ({self.max_open_trades}) reached.")
            return True

        # Simplified risk calculation (assuming 2% risk per trade currently)
        total_current_risk = sum([float(trade['position_size']) for trade in open_trades]) / capital # Approximated %

        if total_current_risk + current_risk_pct > self.max_risk_exposure:
             logger.info(f"Global Limit Veto: Max risk exposure ({self.max_risk_exposure*100}%) reached.")
             return True

        return False
