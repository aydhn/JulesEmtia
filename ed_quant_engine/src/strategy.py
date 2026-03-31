import pandas as pd
import numpy as np
from typing import Dict, Optional
from src.logger import logger

class Strategy:
    def __init__(self, atr_sl_multiplier: float = 1.5, atr_tp_multiplier: float = 3.0, default_capital: float = 10000.0, max_risk_pct: float = 0.02):
        self.atr_sl_multiplier = atr_sl_multiplier
        self.atr_tp_multiplier = atr_tp_multiplier
        self.default_capital = default_capital
        self.max_risk_pct = max_risk_pct

    def generate_signal(self, ticker: str, df: pd.DataFrame) -> Optional[Dict]:
        """
        Generates trading signals using confluent indicators and strict lookahead bias prevention.
        Uses vectorized operations to check logic on the last completely closed candle.
        """
        # Strictly use shift(1) logic implicitly by checking the LAST row of the provided DataFrame
        # (Assuming the main loop only provides fully closed candles).
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]

        current_price = last_row['Close']
        ema_50 = last_row['EMA_50']
        rsi_14 = last_row['RSI_14']
        macd_hist = last_row['MACD_Hist']
        bb_lower = last_row['BB_Lower']
        bb_upper = last_row['BB_Upper']
        atr = last_row['ATR_14']

        # Determine Trend
        is_uptrend = current_price > ema_50
        is_downtrend = current_price < ema_50

        # Oscillators (Confluence)
        rsi_oversold = prev_row['RSI_14'] < 30 and rsi_14 >= 30 # RSI crossed up
        rsi_overbought = prev_row['RSI_14'] > 70 and rsi_14 <= 70 # RSI crossed down

        price_touch_lower_bb = prev_row['Low'] <= prev_row['BB_Lower'] and last_row['Close'] > bb_lower
        price_touch_upper_bb = prev_row['High'] >= prev_row['BB_Upper'] and last_row['Close'] < bb_upper

        macd_positive_crossover = prev_row['MACD_Hist'] <= 0 and macd_hist > 0
        macd_negative_crossover = prev_row['MACD_Hist'] >= 0 and macd_hist < 0

        signal = None
        direction = None

        # Long Signal Logic
        if is_uptrend and (rsi_oversold or price_touch_lower_bb) and macd_positive_crossover:
            direction = "Long"
            sl_price = current_price - (self.atr_sl_multiplier * atr)
            tp_price = current_price + (self.atr_tp_multiplier * atr)
            signal = 1

        # Short Signal Logic
        elif is_downtrend and (rsi_overbought or price_touch_upper_bb) and macd_negative_crossover:
            direction = "Short"
            sl_price = current_price + (self.atr_sl_multiplier * atr)
            tp_price = current_price - (self.atr_tp_multiplier * atr)
            signal = -1

        if signal:
            # Position Sizing
            risk_amount = self.default_capital * self.max_risk_pct
            sl_distance = abs(current_price - sl_price)
            if sl_distance > 0:
                position_size = risk_amount / sl_distance
            else:
                position_size = 0
                logger.warning(f"SL distance is zero for {ticker}. Skipping trade.")
                return None

            return {
                "ticker": ticker,
                "direction": direction,
                "entry_price": current_price,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "position_size": position_size,
                "signal_type": signal
            }

        return None

