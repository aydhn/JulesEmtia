import pandas as pd
import numpy as np
from config import GLOBAL_EXPOSURE_LIMIT, MAX_POSITIONS, CORRELATION_THRESHOLD
from core.paper_db import PaperDB
from core.logger import get_logger

logger = get_logger()

class PortfolioManager:
    def __init__(self, db: PaperDB):
        self.db = db

    def check_correlation_veto(self, new_ticker: str, direction: str, universe_cache: dict) -> bool:
        """Returns True if highly correlated with an existing open position."""
        open_positions = self.db.fetch_all("SELECT ticker, direction FROM trades WHERE status = 'Open'")
        if len(open_positions) >= MAX_POSITIONS:
            logger.warning(f"{new_ticker} Sinyali Reddedildi: Maksimum Açık Pozisyon ({MAX_POSITIONS}) Limitine Ulaşıldı.")
            return True

        if len(open_positions) == 0: return False

        new_df = universe_cache.get(new_ticker)
        if new_df is None: return True

        for (open_ticker, open_dir) in open_positions:
            open_df = universe_cache.get(open_ticker)
            if open_df is None: continue

            # Combine last 30 closes for correlation
            combined = pd.concat([new_df['Close'].tail(30), open_df['Close'].tail(30)], axis=1)
            combined.columns = [new_ticker, open_ticker]
            corr = combined.corr().iloc[0, 1]

            if abs(corr) > CORRELATION_THRESHOLD:
                if (corr > 0 and direction == open_dir) or (corr < 0 and direction != open_dir):
                    logger.info(f"{new_ticker} Sinyali Korelasyon Vetosu Yedi. ({open_ticker} ile korelasyon: {corr:.2f})")
                    return True

        return False

    def calculate_kelly_position(self, capital: float, entry_price: float, sl_price: float) -> float:
        """Fractional Kelly Criterion + Hard Caps."""
        closed_trades = self.db.fetch_all("SELECT pnl FROM trades WHERE status = 'Closed'")
        wins = [t[0] for t in closed_trades if t[0] > 0]
        losses = [abs(t[0]) for t in closed_trades if t[0] < 0]

        if not wins or not losses:
            f_star = 0.01 # Default to 1% if no history
        else:
            win_rate = len(wins) / len(closed_trades)
            avg_win = np.mean(wins)
            avg_loss = np.mean(losses)

            b = avg_win / avg_loss if avg_loss > 0 else 1.0
            p = win_rate
            q = 1 - p

            # Full Kelly = (bp - q) / b
            f_star = (b * p - q) / b if b > 0 else 0

        # Fractional Kelly (Half Kelly) to reduce variance & drawdown
        f_star = f_star / 2

        # Hard Caps
        f_star = max(0.005, min(f_star, GLOBAL_EXPOSURE_LIMIT)) # Between 0.5% and Max 6%

        risk_amount = capital * f_star
        sl_distance = abs(entry_price - sl_price)

        if sl_distance <= 0: return 0.0

        position_size = risk_amount / sl_distance
        return position_size
