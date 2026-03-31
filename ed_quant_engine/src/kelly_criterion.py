from typing import Dict, List
import pandas as pd
from src.paper_db import db
from src.logger import logger

class KellyCalculator:
    def __init__(self, fraction: float = 0.5, max_cap: float = 0.05, min_history: int = 20):
        self.fraction = fraction # Half Kelly
        self.max_cap = max_cap   # Hard Cap 5%
        self.min_history = min_history

    def get_fractional_kelly(self) -> float:
        """
        Calculates Kelly fraction based on historical closed trades.
        f* = (bp - q) / b
        Returns the capped fractional Kelly percentage.
        """
        try:
            db.cursor.execute("SELECT pnl FROM trades WHERE status = 'Closed' AND pnl IS NOT NULL")
            results = db.cursor.fetchall()
            pnls = [row[0] for row in results]

            if len(pnls) < self.min_history:
                logger.info(f"Insufficient history for Kelly ({len(pnls)}/{self.min_history}). Using default risk.")
                return 0.02 # Default 2%

            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p <= 0]

            p = len(wins) / len(pnls)
            q = 1 - p

            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = abs(sum(losses) / len(losses)) if losses else 0

            b = avg_win / avg_loss if avg_loss > 0 else float('inf')

            if b == 0: return 0.01 # Edge case

            kelly_f = (b * p - q) / b
            fractional_kelly = kelly_f * self.fraction

            if fractional_kelly <= 0:
                 logger.warning(f"Negative Kelly ({fractional_kelly:.4f}). Edge lost. Using minimum risk.")
                 return 0.005 # Min risk

            # Apply Hard Cap
            final_risk = min(fractional_kelly, self.max_cap)
            logger.info(f"Kelly Calculated: {final_risk*100:.2f}% (Cap: {self.max_cap*100}%, Fraction: {self.fraction})")
            return final_risk

        except Exception as e:
            logger.error(f"Kelly calculation failed: {e}. Using default 2%.")
            return 0.02
