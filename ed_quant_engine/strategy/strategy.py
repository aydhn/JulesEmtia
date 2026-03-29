import pandas as pd
import numpy as np
from ed_quant_engine.core.logger import logger
from typing import Dict, Optional, Tuple

class MovingAverageCrossStrategy:
    """
    Core Strategy Engine. Combines MTF Confluence and Vectorized Signal Generation.
    Strictly follows SOLID and "No Lookahead Bias" rules.
    """
    def __init__(self, atr_multiplier_sl: float = 1.5, atr_multiplier_tp: float = 3.0, risk_reward_ratio: float = 2.0):
        self.atr_sl = atr_multiplier_sl
        self.atr_tp = atr_multiplier_tp
        self.rr = risk_reward_ratio

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates 1 for Long, -1 for Short, 0 for Neutral.
        Vectorized operations (np.where) to avoid slow loops.
        Uses shifted columns (.shift(1)) to ensure we only trade on confirmed, closed candles.
        """
        if df.empty or 'htf_ema_50' not in df.columns:
            return df

        data = df.copy()

        # We need the values of the previous closed hourly candle
        # and the previous closed daily candle (which is already shifted by align_timeframes).

        c = data['close'].shift(1)
        prev_rsi = data['rsi_14'].shift(1)
        prev_macd = data['macd_hist'].shift(1)
        prev_macd_signal = data['macd_signal'].shift(1)
        prev_bb_lower = data['bb_lower'].shift(1)
        prev_bb_upper = data['bb_upper'].shift(1)

        # HTF (Daily) Trend Veto
        htf_trend_up = (data['htf_close'] > data['htf_ema_50']) & (data['htf_macd_hist'] > 0)
        htf_trend_down = (data['htf_close'] < data['htf_ema_50']) & (data['htf_macd_hist'] < 0)

        # LTF (Hourly) Triggers
        # RSI crossover 30 or BB Lower Touch
        long_trigger = ((prev_rsi > 30) & (data['rsi_14'].shift(2) <= 30)) | (data['low'].shift(1) <= prev_bb_lower)
        # MACD positive or crossover
        long_momentum = prev_macd > 0

        short_trigger = ((prev_rsi < 70) & (data['rsi_14'].shift(2) >= 70)) | (data['high'].shift(1) >= prev_bb_upper)
        short_momentum = prev_macd < 0

        # Confluence
        is_long = htf_trend_up & long_trigger & long_momentum
        is_short = htf_trend_down & short_trigger & short_momentum

        data['signal'] = 0
        data.loc[is_long, 'signal'] = 1
        data.loc[is_short, 'signal'] = -1

        return data

    def calculate_position_size(self, capital: float, entry_price: float, sl_price: float, risk_pct: float) -> float:
        """
        Standard Position Sizing: Risk Amount / Distance to SL.
        Kelly Criterion will override this later in the pipeline.
        """
        risk_amount = capital * risk_pct
        sl_distance = abs(entry_price - sl_price)

        if sl_distance == 0:
            return 0.0

        position_size = risk_amount / sl_distance
        return position_size

    def get_trade_parameters(self, row: pd.Series, direction: int) -> Tuple[float, float, float]:
        """
        Returns Entry, SL, TP based on JP Morgan Risk Alg (Dynamic ATR).
        """
        # Entry price is current candle OPEN (assuming we enter at market open right after the signal candle closes)
        entry_price = row['open']
        atr = row['atr_14']

        if direction == 1:
            sl_price = entry_price - (self.atr_sl * atr)
            tp_price = entry_price + (self.atr_tp * atr)
        else:
            sl_price = entry_price + (self.atr_sl * atr)
            tp_price = entry_price - (self.atr_tp * atr)

        return entry_price, sl_price, tp_price
