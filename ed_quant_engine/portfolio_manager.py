import pandas as pd
import numpy as np
import sqlite3
import config
from logger import logger

class PortfolioManager:
    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self.max_positions = 4
        self.max_global_exposure_pct = 0.06 # 6% max total risk

    def calculate_correlation_matrix(self, returns_df: pd.DataFrame, period=30):
        ''' Phase 11: Dynamic Correlation Matrix '''
        if returns_df.empty or len(returns_df) < period:
            return pd.DataFrame()
        return returns_df.tail(period).corr(method='pearson')

    async def fetch_daily_returns_matrix(self, tickers: list, period="3mo") -> pd.DataFrame:
        import yfinance as yf
        import asyncio
        try:
            # Download concurrently to avoid blocking
            data = await asyncio.to_thread(yf.download, tickers, period=period, interval="1d", progress=False)
            if 'Close' in data.columns:
                 closes = data['Close']
                 # Calculate daily pct change
                 returns_df = closes.pct_change().dropna()
                 return returns_df
        except Exception as e:
            logger.error(f"Error fetching correlation matrix returns: {e}")
        return pd.DataFrame()

    def correlation_veto(self, new_ticker: str, new_direction: str, open_positions: list, corr_matrix: pd.DataFrame, threshold=0.75) -> bool:
        ''' Phase 11: Risk Duplication Filter '''
        if corr_matrix.empty or new_ticker not in corr_matrix.columns:
            return False

        for pos in open_positions:
            existing_ticker = pos['ticker']
            existing_dir = pos['direction']

            if existing_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, existing_ticker]

                # If high positive correlation and same direction -> VETO
                if corr > threshold and new_direction == existing_dir:
                     logger.warning(f"Correlation Veto: {new_ticker} ({new_direction}) is highly correlated ({corr:.2f}) with open {existing_ticker} ({existing_dir}).")
                     return True

                # If high negative correlation and opposite direction -> VETO
                elif corr < -threshold and new_direction != existing_dir:
                     logger.warning(f"Correlation Veto: {new_ticker} ({new_direction}) is negatively correlated ({corr:.2f}) with open {existing_ticker} ({existing_dir}). Risk duplicated.")
                     return True

        return False

    def get_kelly_fraction(self, recent_trades: list) -> float:
        ''' Phase 15: Fractional Kelly Criterion '''
        if not recent_trades or len(recent_trades) < 10:
             return 0.02 # Default fallback risk

        wins = [t for t in recent_trades if t['pnl'] > 0]
        losses = [t for t in recent_trades if t['pnl'] <= 0]

        p = len(wins) / len(recent_trades)
        q = 1 - p

        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 1

        if avg_loss == 0: return 0.02

        b = avg_win / avg_loss

        if b == 0: return 0.0

        # Kelly Formula: f = (bp - q) / b
        f_star = (b * p - q) / b

        # JP Morgan Risk: Half-Kelly
        fractional_kelly = f_star / 2.0

        # Hard Cap at 4%
        fractional_kelly = min(max(fractional_kelly, 0.005), 0.04)

        return fractional_kelly

    def calculate_position_size(self, account_balance: float, entry_price: float, sl_price: float, recent_trades: list) -> float:
        ''' Calculates unit size based on Kelly risk % and distance to Stop Loss. '''
        risk_pct = self.get_kelly_fraction(recent_trades)
        capital_at_risk = account_balance * risk_pct

        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0: return 0.0

        position_size = capital_at_risk / sl_distance
        return position_size

    def check_global_limits(self, open_positions: list) -> bool:
        if len(open_positions) >= self.max_positions:
             logger.warning(f"Global Limit Veto: Max positions ({self.max_positions}) reached.")
             return False
        return True

portfolio_manager = PortfolioManager()
