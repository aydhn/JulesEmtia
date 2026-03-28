import pandas as pd
from core.logger import setup_logger
from typing import Dict, Optional, Tuple

logger = setup_logger("strategy")

class StrategyEngine:
    """
    Core strategy logic combining Multi-Timeframe Confluence, Technical Indicators,
    and calculating Entry, Dynamic SL, and TP.
    """
    def __init__(self):
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.sl_atr_multiplier = 1.5
        self.tp_atr_multiplier = 3.0

    def check_signal(self, htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> Optional[Dict]:
        """
        Checks for a MTF confluence signal on the latest closed candle.
        Returns a dictionary with trade details if a signal exists, else None.
        """
        # --- 1. Multi-Timeframe (MTF) Alignment (Master Veto) ---
        # Get the latest completed daily candle
        if len(htf_df) < 2 or len(ltf_df) < 2:
            return None

        # The latest HTF candle might be incomplete today. Use the previous closed day (-2).
        htf_prev_close = htf_df['close'].iloc[-2]
        htf_prev_ema50 = htf_df['ema_50_prev'].iloc[-1] # Assuming features applied
        htf_prev_macd = htf_df['MACDh_12_26_9_prev'].iloc[-1]

        htf_trend_long = (htf_prev_close > htf_prev_ema50) and (htf_prev_macd > 0)
        htf_trend_short = (htf_prev_close < htf_prev_ema50) and (htf_prev_macd < 0)

        # --- 2. Lower Timeframe (LTF) Trigger ---
        # Get the latest shifted indicators (representing the state AT the close of the previous hour)
        ltf_latest = ltf_df.iloc[-1]

        # Note: We use '_prev' columns because we are making a decision AT the open of the current candle,
        # based solely on the closed data of the PREVIOUS candle.
        close_prev = ltf_df['close'].iloc[-2] # Actual price of previous candle
        ema_50 = ltf_latest['ema_50_prev']
        rsi = ltf_latest['rsi_14_prev']
        macd_hist = ltf_latest['MACDh_12_26_9_prev']
        bbl = ltf_latest['BBL_20_2.0_prev']
        bbu = ltf_latest['BBU_20_2.0_prev']

        signal = 0 # 0: None, 1: Long, -1: Short

        # Long Logic
        if htf_trend_long:
            # RSI crossing up from oversold OR touching Lower Bollinger Band
            if (rsi < self.rsi_oversold) or (close_prev <= bbl):
                if macd_hist > 0: # MACD confirmation
                    signal = 1

        # Short Logic
        elif htf_trend_short:
            # RSI crossing down from overbought OR touching Upper Bollinger Band
            if (rsi > self.rsi_overbought) or (close_prev >= bbu):
                if macd_hist < 0: # MACD confirmation
                    signal = -1

        if signal == 0:
            return None

        # --- 3. Dynamic Risk Calculation (ATR based SL/TP) ---
        # Current open price is our theoretical entry
        entry_price = ltf_latest['close']
        current_atr = ltf_latest['atr_14_prev']

        if pd.isna(current_atr) or current_atr <= 0:
            logger.warning("Invalid ATR value, rejecting signal.")
            return None

        if signal == 1:
            sl_price = entry_price - (current_atr * self.sl_atr_multiplier)
            tp_price = entry_price + (current_atr * self.tp_atr_multiplier)
            direction = "Long"
        else:
            sl_price = entry_price + (current_atr * self.sl_atr_multiplier)
            tp_price = entry_price - (current_atr * self.tp_atr_multiplier)
            direction = "Short"

        # Enforce RR ratio of at least 1:2
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        if reward / risk < 1.9:
            logger.warning(f"Rejected {direction} signal due to poor R:R ratio ({reward/risk:.2f})")
            return None

        return {
            "direction": direction,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "atr": current_atr,
            "signal_source": "MTF_Confluence"
        }
