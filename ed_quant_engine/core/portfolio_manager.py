import pandas as pd
import numpy as np
from typing import List, Dict
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config

logger = setup_logger("PortfolioManager")

class PortfolioManager:
    def __init__(self):
        self.max_positions = Config.MAX_OPEN_POSITIONS
        self.max_risk_pct = Config.MAX_PORTFOLIO_RISK_PCT
        self.base_capital = Config.BASE_CAPITAL
        self.correlation_matrix = pd.DataFrame()

    def update_correlation_matrix(self, price_data: Dict[str, pd.DataFrame], window=30):
        """Calculates 30-day rolling Pearson correlation matrix for the universe."""
        try:
            closes = {}
            for ticker, dfs in price_data.items():
                if not dfs['HTF'].empty:
                     closes[ticker] = dfs['HTF']['Close'].tail(window)

            if closes:
                df_closes = pd.DataFrame(closes)
                self.correlation_matrix = df_closes.corr(method='pearson')
                logger.info("Correlation matrix updated.")
        except Exception as e:
            logger.error(f"Failed to update correlation matrix: {e}")

    def correlation_veto(self, new_ticker: str, new_direction: str, open_positions: List[Dict], threshold=0.75) -> bool:
        """Vetoes signal if highly correlated with an existing open position in same direction."""
        if self.correlation_matrix.empty or new_ticker not in self.correlation_matrix.columns:
             return False

        for pos in open_positions:
            existing_ticker = pos['ticker']
            existing_dir = pos['direction']

            if existing_ticker in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[new_ticker, existing_ticker]

                # Risk Duplication Filter
                if abs(corr) >= threshold and new_direction == existing_dir:
                    logger.warning(f"Correlation Veto: {new_ticker} is highly correlated ({corr:.2f}) with open {existing_ticker}")
                    return True
        return False

    def calculate_fractional_kelly(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculates Half-Kelly optimal position sizing fraction."""
        if avg_loss == 0 or win_rate == 0:
            return 0.01 # Fallback minimal risk

        b = avg_win / abs(avg_loss)
        p = win_rate
        q = 1 - p

        kelly_pct = (b * p - q) / b

        if kelly_pct <= 0:
             logger.warning(f"Kelly <= 0. Edge lost. Halting sizing.")
             return 0.005 # Cap at 0.5% risk if edge is negative

        half_kelly = kelly_pct / 2.0

        # Hard Cap Protection (Phase 15)
        return min(half_kelly, 0.04) # Max 4% absolute risk per trade

    def get_position_size(self, signal: dict, current_capital: float, win_stats: dict) -> float:
        """Returns recommended lot size / dollar risk amount."""
        wr = win_stats.get('win_rate', 0.5)
        aw = win_stats.get('avg_win', 2.0)
        al = win_stats.get('avg_loss', 1.0)

        risk_fraction = self.calculate_fractional_kelly(wr, aw, al)
        risk_amount = current_capital * risk_fraction

        sl_distance = abs(signal['entry_price'] - signal['sl_price'])
        if sl_distance == 0:
            return 0.0

        position_size = risk_amount / sl_distance
        logger.info(f"Position Sizing: Risk Amount ${risk_amount:.2f} ({risk_fraction*100:.1f}%), Size: {position_size:.4f}")
        return position_size

    def global_limit_veto(self, open_positions_count: int) -> bool:
        if open_positions_count >= self.max_positions:
             logger.warning(f"Global Limit Veto: Max positions ({self.max_positions}) reached.")
             return True
        return False
