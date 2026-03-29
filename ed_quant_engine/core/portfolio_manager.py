import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from ed_quant_engine.core.logger import logger

class PortfolioManager:
    """
    Advanced Portfolio Allocation, Correlation Engine & Kelly Criterion.
    Enforces risk exposure limits and prevents duplicate risks.
    """
    def __init__(self, max_positions: int = 4, max_risk_pct: float = 0.06, correlation_threshold: float = 0.75):
        self.max_positions = max_positions
        self.max_risk_pct = max_risk_pct
        self.corr_threshold = correlation_threshold

    def calculate_correlation_matrix(self, price_data: pd.DataFrame, window: int = 30) -> pd.DataFrame:
        """
        Dynamically calculates rolling Pearson correlation between all traded assets.
        Input should be a DataFrame where columns are Tickers and values are daily closing prices.
        """
        returns = price_data.pct_change().dropna()
        return returns.tail(window).corr()

    def correlation_veto(self, new_ticker: str, new_direction: str, open_positions: List[Dict], corr_matrix: pd.DataFrame) -> bool:
        """
        Risk Duplication Filter. Rejects trades highly correlated with open trades in the same direction.
        Returns True if signal is VETOED.
        """
        if corr_matrix.empty or new_ticker not in corr_matrix.columns:
            return False # Assume uncorrelated

        for pos in open_positions:
            open_ticker = pos['ticker']
            open_dir = pos['direction']

            if open_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, open_ticker]

                # Positive Correlation + Same Direction = Double Risk (VETO)
                if corr > self.corr_threshold and open_dir == new_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} is highly correlated ({corr:.2f}) with open {open_ticker}")
                    return True

                # Negative Correlation + Opposite Direction = Double Risk (VETO)
                if corr < -self.corr_threshold and open_dir != new_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} is inversely correlated ({corr:.2f}) with open {open_ticker}")
                    return True

        return False

    def check_exposure_limits(self, open_positions: List[Dict], capital: float) -> bool:
        """
        Global Risk Limit Veto.
        Returns True if exposure limits are exceeded (VETOED).
        """
        if len(open_positions) >= self.max_positions:
            logger.warning(f"Exposure Limit Veto: Max open positions reached ({self.max_positions})")
            return True

        # Calculate total risk at stake
        total_risk = sum(abs(pos['entry_price'] - pos['sl_price']) * pos['position_size'] for pos in open_positions)

        if total_risk / capital >= self.max_risk_pct:
            logger.warning(f"Exposure Limit Veto: Max portfolio risk exceeded ({total_risk/capital*100:.2f}% >= {self.max_risk_pct*100}%)")
            return True

        return False

    def calculate_kelly_fraction(self, closed_trades: pd.DataFrame, max_cap: float = 0.04) -> float:
        """
        Fractional Kelly Criterion calculation based on actual historical performance.
        Returns the % of capital to risk on the next trade (e.g., 0.02 for 2%).
        """
        if closed_trades.empty or len(closed_trades) < 5:
            return 0.01 # Default to 1% if insufficient history

        wins = closed_trades[closed_trades['pnl'] > 0]
        losses = closed_trades[closed_trades['pnl'] < 0]

        # Win Rate (p)
        p = len(wins) / len(closed_trades)
        q = 1 - p

        # Average Win / Average Loss (b)
        avg_win = wins['pnl'].mean() if not wins.empty else 0.0
        avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 0.0

        if avg_loss == 0:
            return max_cap

        b = avg_win / avg_loss

        # Full Kelly (f*)
        f = (b * p - q) / b

        # JP Morgan Risk Mitigation: Half Kelly
        half_kelly = f / 2.0

        # If negative Kelly (strategy is losing edge), drastically reduce risk
        if half_kelly <= 0:
            return 0.005 # Minimal risk

        # Hard Cap Protection
        return min(half_kelly, max_cap)
