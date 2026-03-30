import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from execution_model import ExecutionSimulator
from portfolio_manager import PortfolioManager
from ml_validator import MLValidator
from sentiment_filter import SentimentFilter
from logger import logger

class QuantStrategy:
    """
    Core Logic Engine (Phase 4, 16).
    Applies strict Confluence rules and Multi-Timeframe (MTF) analysis.
    Prevents Lookahead Bias by strictly using shifted data (closed candles).
    Outputs actionable signals with dynamic ATR risk levels.
    """

    @staticmethod
    def _evaluate_htf(daily_df: pd.DataFrame) -> int:
        """
        Master Veto: Daily Trend Filter.
        0: No Trend, 1: Bullish, -1: Bearish
        """
        if daily_df.empty or len(daily_df) < 2:
            return 0

        # ALWAYS use the previous closed daily candle to prevent lookahead bias
        prev_day = daily_df.iloc[-2]

        # Bullish: Price > EMA50 AND MACD > 0
        if prev_day['Close'] > prev_day['EMA_50'] and prev_day['MACD'] > 0:
            return 1

        # Bearish: Price < EMA50 AND MACD < 0
        if prev_day['Close'] < prev_day['EMA_50'] and prev_day['MACD'] < 0:
            return -1

        return 0

    @classmethod
    async def generate_signal(cls, ticker: str, hourly_df: pd.DataFrame, daily_df: pd.DataFrame, corr_matrix: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Runs the full MTF Confluence Pipeline.
        1. HTF Trend Veto
        2. LTF Sniper Entry
        3. Dynamic SL/TP (ATR)
        4. ML & Sentiment Validation
        5. Portfolio & Execution Math
        """
        if hourly_df.empty or len(hourly_df) < 2:
            return None

        # 1. Master Veto (HTF)
        htf_trend = cls._evaluate_htf(daily_df)
        if htf_trend == 0:
            logger.debug(f"{ticker}: Choppy daily trend. Vetoed.")
            return None

        # 2. LTF Sniper Entry (Use prev closed 1H candle)
        prev_hour = hourly_df.iloc[-2]
        current_hour_open = hourly_df.iloc[-1]['Open'] # For execution price base

        signal_dir = 0

        # Long Confluence: HTF Bullish + RSI crossing up from 30 OR touching Lower BB
        if htf_trend == 1:
            rsi_cross = prev_hour['RSI_14'] < 30 and hourly_df.iloc[-3]['RSI_14'] >= 30
            bb_touch = prev_hour['Low'] <= prev_hour['BBL_20_2.0']

            if rsi_cross or bb_touch:
                signal_dir = 1

        # Short Confluence: HTF Bearish + RSI crossing down from 70 OR touching Upper BB
        elif htf_trend == -1:
            rsi_cross = prev_hour['RSI_14'] > 70 and hourly_df.iloc[-3]['RSI_14'] <= 70
            bb_touch = prev_hour['High'] >= prev_hour['BBU_20_2.0']

            if rsi_cross or bb_touch:
                signal_dir = -1

        if signal_dir == 0:
            return None

        logger.info(f"TECHNICAL CONFLUENCE: {ticker} -> {'LONG' if signal_dir == 1 else 'SHORT'}")

        # 3. Dynamic Risk Management (JP Morgan standards)
        atr = prev_hour['ATR_14']

        # Execution Modeling (Spread + Slippage applied to Entry, SL, TP)
        # We assume we enter at Current Hour Open + Cost
        exec_entry = ExecutionSimulator.execute_trade_price(ticker, current_hour_open, signal_dir, hourly_df['ATR_14'])

        if signal_dir == 1:
            # Long SL/TP
            sl_raw = exec_entry - (1.5 * atr)
            tp_raw = exec_entry + (3.0 * atr)

            exec_sl = ExecutionSimulator.execute_trade_price(ticker, sl_raw, -1, hourly_df['ATR_14']) # Selling to close
            exec_tp = ExecutionSimulator.execute_trade_price(ticker, tp_raw, -1, hourly_df['ATR_14'])
        else:
            # Short SL/TP
            sl_raw = exec_entry + (1.5 * atr)
            tp_raw = exec_entry - (3.0 * atr)

            exec_sl = ExecutionSimulator.execute_trade_price(ticker, sl_raw, 1, hourly_df['ATR_14']) # Buying to close
            exec_tp = ExecutionSimulator.execute_trade_price(ticker, tp_raw, 1, hourly_df['ATR_14'])

        # 4. ML Validation
        is_approved, prob = MLValidator.validate_signal(prev_hour)
        if not is_approved:
            return None

        # 5. NLP Sentiment Veto
        sentiment_veto = await SentimentFilter.check_sentiment_veto(ticker, signal_dir)
        if sentiment_veto:
            return None

        # 6. Portfolio & Correlation Veto
        if PortfolioManager.check_global_limits():
            return None

        corr_veto = await PortfolioManager.check_correlation_veto(ticker, signal_dir, corr_matrix)
        if corr_veto:
            return None

        # Return structured signal
        return {
            "ticker": ticker,
            "direction": "Long" if signal_dir == 1 else "Short",
            "entry_price": exec_entry,
            "sl_price": exec_sl,
            "tp_price": exec_tp,
            "prob": prob,
            "atr": atr
        }

