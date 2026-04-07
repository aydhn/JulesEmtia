import pandas as pd
import numpy as np
from typing import Dict, List
from .logger import quant_logger
from .config import MAX_POSITIONS, MAX_GLOBAL_RISK_PCT

class PortfolioManager:
    @staticmethod
    def calculate_correlation_matrix(historical_data: Dict[str, pd.DataFrame], lookback: int = 30) -> pd.DataFrame:
        """Calculates rolling correlation matrix of daily closes."""
        closes = {}
        for ticker, df in historical_data.items():
            if df is not None and not df.empty:
                # Use daily HTF close if available, else standard close
                col = 'Close_HTF' if 'Close_HTF' in df.columns else 'Close'
                closes[ticker] = df[col].tail(lookback)

        if not closes:
            return pd.DataFrame()

        prices_df = pd.DataFrame(closes).fillna(method='ffill')
        return prices_df.corr()

    @staticmethod
    def correlation_veto(ticker: str, direction: str, open_positions: List[Dict], corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
        """
        Returns True if signal is VETOED due to high correlation with existing open position.
        """
        if corr_matrix.empty or ticker not in corr_matrix.columns:
            return False

        for pos in open_positions:
            open_ticker = pos['ticker']
            open_dir = pos['direction']

            if open_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[ticker, open_ticker]

                # If highly correlated and same direction -> VETO (Risk Duplication)
                if corr > threshold and direction == open_dir:
                    quant_logger.warning(f"Correlation VETO: {ticker} ({direction}) highly correlated ({corr:.2f}) with open {open_ticker}.")
                    return True
                # If highly inversely correlated and opposite direction -> VETO
                if corr < -threshold and direction != open_dir:
                    quant_logger.warning(f"Inverse Correlation VETO: {ticker} highly inversely correlated with {open_ticker}.")
                    return True
        return False

    @staticmethod
    def calculate_kelly_fraction(closed_trades: pd.DataFrame) -> float:
        """
        Calculates Fractional Kelly (Half-Kelly).
        f* = (bp - q) / b
        """
        if closed_trades.empty or len(closed_trades) < 10:
            return 0.01 # Default safe fraction (1%)

        wins = closed_trades[closed_trades['net_pnl'] > 0]
        losses = closed_trades[closed_trades['net_pnl'] <= 0]

        p = len(wins) / len(closed_trades)
        q = 1.0 - p

        avg_win = wins['net_pnl'].mean() if not wins.empty else 0.0
        avg_loss = abs(losses['net_pnl'].mean()) if not losses.empty else 1.0 # prevent div zero

        if avg_loss == 0: return 0.01

        b = avg_win / avg_loss

        kelly = (b * p - q) / b

        if kelly <= 0:
            return 0.005 # Minimal risk if edge is lost

        # JP Morgan Risk Algısı: Half-Kelly with Hard Cap
        fractional_kelly = kelly / 2.0
        return min(fractional_kelly, 0.04) # Max 4% per trade hard cap

    @staticmethod
    def get_position_size(balance: float, entry_price: float, sl_price: float, fractional_kelly: float) -> float:
        risk_amount = balance * fractional_kelly
        stop_distance = abs(entry_price - sl_price)
        if stop_distance == 0: return 0.0

        size = risk_amount / stop_distance
        return size
