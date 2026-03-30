import pandas as pd
import numpy as np
import asyncio
from typing import Dict, Optional, Tuple
from paper_db import PaperDB
from logger import logger

class PortfolioManager:
    """
    Phase 11 & 15: Advanced Portfolio Allocation, Correlation Veto, & Kelly Criterion.
    Controls Risk Duplication and dynamically sizes positions based on win probabilities.
    Zero-budget, pure math implementation.
    """

    # Global Limits
    MAX_OPEN_POSITIONS = 4
    MAX_PORTFOLIO_RISK_PCT = 0.06 # Max 6% of account risked at any one time

    @classmethod
    async def calculate_correlation_matrix(cls, universe_data: Dict[str, pd.DataFrame], periods: int = 30) -> pd.DataFrame:
        """
        Dynamically calculates rolling Pearson Correlation Matrix for the last N days.
        Uses Daily (1D) closes.
        """
        closes = {}
        for name, data in universe_data.items():
            if data is not None and not data.empty:
                closes[name] = data['Close'].tail(periods)

        if not closes:
            return pd.DataFrame()

        df_closes = pd.DataFrame(closes)

        # Pearson correlation (-1.0 to 1.0)
        corr_matrix = await asyncio.to_thread(df_closes.corr, method='pearson')
        return corr_matrix

    @classmethod
    async def check_correlation_veto(cls, ticker_name: str, direction: int, corr_matrix: pd.DataFrame, threshold: float = 0.75) -> bool:
        """
        Prevents risk duplication.
        If a highly correlated asset is already open in the same direction, VETO the new signal.
        """
        if corr_matrix.empty or ticker_name not in corr_matrix.columns:
            return False

        # Get currently open trades
        open_trades = PaperDB.fetch_all("SELECT ticker, direction FROM trades WHERE status = 'Open'")

        for trade in open_trades:
            open_ticker = trade['ticker']
            open_direction = 1 if trade['direction'] == 'Long' else -1

            if open_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[ticker_name, open_ticker]

                # Risk Duplication (Same direction, high positive correlation)
                if corr > threshold and direction == open_direction:
                    logger.warning(f"CORRELATION VETO: {ticker_name} rejected. Highly correlated ({corr:.2f}) with open trade {open_ticker}.")
                    return True

                # Risk Duplication (Opposite direction, high negative correlation - e.g. longing USDJPY, shorting EURUSD)
                if corr < -threshold and direction != open_direction:
                    logger.warning(f"CORRELATION VETO: {ticker_name} rejected. Strongly negatively correlated ({corr:.2f}) with open trade {open_ticker} in opposite direction.")
                    return True

        return False

    @classmethod
    def check_global_limits(cls) -> bool:
        """
        Checks if the global portfolio limits are breached.
        Returns True if limits are EXCEEDED (cannot open new trades).
        """
        open_trades = PaperDB.fetch_all("SELECT COUNT(*) as count FROM trades WHERE status = 'Open'")
        count = open_trades[0]['count'] if open_trades else 0

        if count >= cls.MAX_OPEN_POSITIONS:
            logger.warning(f"GLOBAL LIMIT VETO: Maximum open positions ({cls.MAX_OPEN_POSITIONS}) reached.")
            return True

        # Optional: Calculate total risk % and veto if > MAX_PORTFOLIO_RISK_PCT
        return False

    @classmethod
    def calculate_kelly_fraction(cls, min_trades: int = 20) -> float:
        """
        Calculates Fractional Kelly Criterion based on recent closed trades.
        Half-Kelly for risk mitigation (JP Morgan standard).
        Formula: f = (bp - q) / b
        """
        closed_trades = PaperDB.fetch_all(
            "SELECT pnl FROM trades WHERE status = 'Closed' ORDER BY exit_time DESC LIMIT ?",
            (50,)
        )

        if len(closed_trades) < min_trades:
            # Default fallback risk (e.g. 1%) if not enough history
            return 0.01

        pnls = [t['pnl'] for t in closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        # Win Rate (p) and Loss Rate (q)
        p = len(wins) / len(pnls)
        q = 1.0 - p

        # Average Win and Average Loss
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = abs(np.mean(losses)) if losses else 1.0 # Avoid div/0

        if avg_loss == 0:
            return 0.01 # Fallback

        # Win/Loss Ratio (b)
        b = avg_win / avg_loss

        # Full Kelly
        kelly_pct = (b * p - q) / b

        if kelly_pct <= 0:
            logger.warning(f"Kelly negative ({kelly_pct:.2%}). Strategy losing edge. Defaulting to minimum risk (0.5%).")
            return 0.005 # Minimum 0.5% risk

        # Fractional Kelly (Half Kelly) for Safety Buffer
        fractional_kelly = kelly_pct / 2.0

        # Hard Cap (Max 4% per trade regardless of Kelly)
        max_cap = 0.04
        safe_kelly = min(fractional_kelly, max_cap)

        logger.info(f"Fractional Kelly Sizing: {safe_kelly:.2%} (WinRate: {p:.2%}, W/L Ratio: {b:.2f})")
        return safe_kelly

    @classmethod
    def calculate_position_size(cls, account_balance: float, entry_price: float, sl_price: float) -> Tuple[float, float]:
        """
        Calculates the exact position size (units/lots) to trade based on Kelly risk %.
        Risk Amount = Balance * Kelly %
        Position Size = Risk Amount / Stop Loss Distance
        Returns (Risk_Amount, Position_Size)
        """
        risk_pct = cls.calculate_kelly_fraction()
        risk_amount = account_balance * risk_pct

        sl_distance = abs(entry_price - sl_price)

        if sl_distance == 0:
            logger.error("Stop Loss distance is zero. Cannot calculate position size.")
            return 0.0, 0.0

        position_size = risk_amount / sl_distance

        return risk_amount, position_size
