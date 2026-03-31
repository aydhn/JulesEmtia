import yfinance as yf
import pandas as pd
import asyncio
import numpy as np
from src.logger import logger
from src.notifier import send_telegram_message

class CircuitBreaker:
    def __init__(self, vix_threshold: float = 35.0, z_score_threshold: float = 4.0):
        self.vix_threshold = vix_threshold
        self.z_score_threshold = z_score_threshold

    async def get_vix_level(self) -> float:
        try:
            vix_df = await asyncio.to_thread(yf.download, tickers="^VIX", period="5d", interval="1d", progress=False)
            if not vix_df.empty:
                return float(vix_df['Close'].iloc[-1]) # .item() extracts scalar from Series/DataFrame cell
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return 0.0

    async def check_black_swan(self) -> bool:
        vix = await self.get_vix_level()
        if vix >= self.vix_threshold:
            msg = f"🚨 *CRITICAL WARNING*: VIX Circuit Breaker Triggered! VIX={vix:.2f} >= {self.vix_threshold}. Entering Defense Mode."
            logger.critical(msg)
            send_telegram_message(msg)
            return True
        return False

    def check_flash_crash(self, ticker: str, df: pd.DataFrame, window: int = 20) -> bool:
        """
        Calculates Z-Score of the current price against a rolling window.
        If the Z-Score is beyond +/- threshold, it's considered an anomaly.
        """
        if df.empty or len(df) < window:
            return False

        # Calculate rolling mean and std dev
        rolling_mean = df['Close'].rolling(window=window).mean()
        rolling_std = df['Close'].rolling(window=window).std()

        # Get latest values
        current_price = df['Close'].iloc[-1]
        mean = rolling_mean.iloc[-1]
        std = rolling_std.iloc[-1]

        if std == 0: # Avoid division by zero
            return False

        z_score = (current_price - mean) / std

        if abs(z_score) >= self.z_score_threshold:
             msg = f"🚨 *ANOMALY DETECTED*: Flash Crash/Spike on {ticker}. Z-Score={z_score:.2f} (Threshold={self.z_score_threshold}). Trading halted for this asset."
             logger.critical(msg)
             send_telegram_message(msg)
             return True

        return False

    def activate_defense_mode(self, current_price: float, trade: dict, atr: float) -> float:
         """
         In a Black Swan event, aggressively trail the stop loss or close the position.
         Returns the aggressive new SL price.
         """
         entry_price = float(trade['entry_price'])
         direction = trade['direction']

         # Aggressive defense: 0.5 ATR instead of 1.5 ATR
         aggressive_atr_mult = 0.5

         if direction == "Long":
             # If profitable, lock in tight stop. If losing, move to breakeven if possible.
             new_sl = current_price - (aggressive_atr_mult * atr)
             if current_price < entry_price:
                  new_sl = entry_price # Try to breakeven if underwater
             return new_sl

         elif direction == "Short":
             new_sl = current_price + (aggressive_atr_mult * atr)
             if current_price > entry_price:
                  new_sl = entry_price
             return new_sl
