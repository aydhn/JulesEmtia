import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.core.macro_filter import MacroRegime

logger = setup_logger("Strategy")

class MTFConfluenceStrategy:
    def __init__(self, risk_reward_ratio=2.0, atr_multiplier=1.5):
        self.risk_reward_ratio = risk_reward_ratio
        self.atr_multiplier = atr_multiplier
        self.macro_filter = MacroRegime()

    def generate_signals(self, merged_df: pd.DataFrame, ticker: str, macro_regime: str) -> Optional[Dict[str, Any]]:
        """
        Generates Buy/Sell signals based on HTF trend alignment and LTF confluence.
        Strict Lookahead Bias prevention: Uses shift(1) for all checks.
        """
        if merged_df.empty or len(merged_df) < 2:
            return None

        # Always check the previous closed candle
        prev_candle = merged_df.iloc[-2]
        current_price = merged_df['Close'].iloc[-1]

        # Flash crash check (Z-Score anomaly on LTF)
        if MacroRegime.flash_crash_check(merged_df, window=50, threshold=4.0):
            logger.warning(f"Strategy Veto: Flash Crash Anomaly on {ticker}")
            return None

        # Extract features for readability
        htf_close = prev_candle.get('HTF_Close', np.nan)
        htf_ema50 = prev_candle.get('HTF_EMA_50', np.nan)

        ltf_close = prev_candle['Close']
        ltf_ema50 = prev_candle['EMA_50']
        ltf_rsi = prev_candle['RSI_14']
        ltf_macd = prev_candle['MACD']
        ltf_bbl = prev_candle['BBL_20_2.0']
        ltf_bbu = prev_candle['BBU_20_2.0']
        ltf_atr = prev_candle['ATR_14']

        # HTF Master Veto (Daily Trend Direction)
        htf_trend_up = htf_close > htf_ema50
        htf_trend_down = htf_close < htf_ema50

        # LTF Confluence Conditions
        ltf_long_cond = (ltf_rsi < 30) or (ltf_close <= ltf_bbl) and (ltf_macd > 0)
        ltf_short_cond = (ltf_rsi > 70) or (ltf_close >= ltf_bbu) and (ltf_macd < 0)

        signal = 0
        direction = ""

        # Long Signal Generation
        if htf_trend_up and ltf_long_cond and ltf_close > ltf_ema50:
            if macro_regime == "Risk_Off" and ("GC=F" in ticker or "SI=F" in ticker):
                 logger.info(f"Macro Veto: Risk-Off regime vetoed Long on {ticker}")
            else:
                 signal = 1
                 direction = "Long"

        # Short Signal Generation
        elif htf_trend_down and ltf_short_cond and ltf_close < ltf_ema50:
             signal = -1
             direction = "Short"

        if signal != 0:
            # Dynamic Stop Loss & Take Profit (JP Morgan Risk)
            sl_dist = ltf_atr * self.atr_multiplier
            if direction == "Long":
                 sl_price = current_price - sl_dist
                 tp_price = current_price + (sl_dist * self.risk_reward_ratio)
            else:
                 sl_price = current_price + sl_dist
                 tp_price = current_price - (sl_dist * self.risk_reward_ratio)

            logger.info(f"Signal Generated: {direction} on {ticker} @ {current_price}")

            return {
                "ticker": ticker,
                "direction": direction,
                "entry_price": current_price,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "atr": ltf_atr
            }

        return None
