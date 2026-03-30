import pandas as pd
import numpy as np
import pandas_ta as ta
from typing import Dict, Any, Tuple
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import math

from .infrastructure import logger, PaperDB
from .config import SPREADS, MAX_RISK_PER_TRADE, GLOBAL_EXPOSURE_LIMIT, TICKERS

# ----------------- TECHNICAL INDICATORS (Phase 3) -----------------
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add MTF indicators using vectorized pandas_ta operations."""
    # Ensure there's enough data for 200 EMA
    if len(df) < 200:
        logger.warning(f"Dataframe too short ({len(df)}) for features.")
        return df

    # Trend Filter (EMA 50 & 200)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)

    # Momentum & RSI
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)

    # Volatility & Risk (ATR & BBands)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)


    # Micro Flash Crash Detection (Phase 19 Z-Score)
    # Z-Score = (Close - SMA(20)) / STD(20)
    sma = df['Close'].rolling(window=20).mean()
    std = df['Close'].rolling(window=20).std()
    df['Z_Score'] = (df['Close'] - sma) / std

    # Price Action (Log Returns)
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    # Drop NaNs after indicator generation (from lookback)
    df.dropna(inplace=True)
    return df

# ----------------- RISK & EXECUTION (Phases 11, 12, 15, 21) -----------------
class RiskManager:
    def __init__(self, db: PaperDB):
        self.db = db

    def calculate_kelly_fraction(self) -> float:
        """Phase 15: Half-Kelly Criterion based on past 50 closed trades."""
        closed_trades = self.db.get_closed_trades()
        if len(closed_trades) < 10:
            # Not enough data, return conservative base risk
            return 0.01

        recent_trades = closed_trades.tail(50)
        wins = recent_trades[recent_trades['pnl'] > 0]
        losses = recent_trades[recent_trades['pnl'] <= 0]

        if len(wins) == 0:
            return 0.0 # Halt trading if complete failure

        p = len(wins) / len(recent_trades)
        q = 1.0 - p

        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 1.0
        b = avg_win / avg_loss

        # Base Kelly Formula
        if b == 0:
            return 0.0

        f_star = (b * p - q) / b

        # Fractional Kelly (Half Kelly)
        fractional_kelly = f_star / 2.0

        # Hard Cap (Phase 15)
        safe_kelly = max(0.005, min(fractional_kelly, MAX_RISK_PER_TRADE))
        logger.info(f"Dynamic Kelly Calculated: p={p:.2f}, b={b:.2f} -> Risk: {safe_kelly:.2%}")
        return safe_kelly

    def calculate_position_size(self, current_price: float, atr: float, balance: float) -> float:
        """Calculate Lot Size based on Kelly % and ATR Stop Distance."""
        risk_pct = self.calculate_kelly_fraction()
        risk_amount = balance * risk_pct
        stop_distance = 1.5 * atr

        if stop_distance <= 0:
            return 0.0

        lot_size = risk_amount / stop_distance
        return round(lot_size, 4)

    def dynamic_spread_slippage(self, ticker: str, current_price: float, atr: float) -> Tuple[float, float]:
        """Phase 21: Dynamic spread and ATR-adjusted slippage."""
        category = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")
        base_spread = SPREADS.get(category, 0.001)

        # Slippage increases if ATR is high (volatile market)
        # Assuming typical ATR is ~0.5% of price, adjust slippage linearly
        volatility_factor = (atr / current_price) / 0.005
        volatility_factor = max(1.0, min(volatility_factor, 3.0)) # Cap at 3x

        slippage = (base_spread * 0.5) * volatility_factor
        return base_spread, slippage

    def check_portfolio_limits(self, new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame) -> bool:
        """Phase 11: Correlation Veto & Global Exposure Limits."""
        open_trades = self.db.get_open_trades()

        # Global Cap
        if len(open_trades) >= GLOBAL_EXPOSURE_LIMIT:
            logger.warning("Global Exposure Limit Reached. Rejecting new signal.")
            return False

        # Correlation Matrix Check (Risk Duplication)
        for _, trade in open_trades.iterrows():
            existing_ticker = trade['ticker']
            existing_dir = trade['direction']

            # If tickers are the same, reject same direction
            if existing_ticker == new_ticker and existing_dir == new_direction:
                return False

            # If correlation > 0.75 and same direction -> Reject
            if new_ticker in corr_matrix.columns and existing_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, existing_ticker]
                if corr > 0.75 and new_direction == existing_dir:
                    logger.warning(f"Correlation Veto: {new_ticker} vs {existing_ticker} (Corr: {corr:.2f})")
                    return False

        return True

    def calculate_trailing_stop(self, direction: str, current_price: float, entry_price: float, current_sl: float, atr: float) -> float:
        """Phase 12: Strictly Monotonic Trailing Stop & Breakeven."""
        new_sl = current_sl

        if direction == "Long":
            # Breakeven check
            if current_price >= entry_price + (1.0 * atr):
                if current_sl < entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")

            # Trailing Stop check
            calculated_sl = current_price - (1.5 * atr)
            if calculated_sl > new_sl: # Strictly monotonic (only move up for Longs)
                new_sl = calculated_sl

        elif direction == "Short":
            # Breakeven check
            if current_price <= entry_price - (1.0 * atr):
                if current_sl > entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")

            # Trailing Stop check
            calculated_sl = current_price + (1.5 * atr)
            if calculated_sl < new_sl: # Strictly monotonic (only move down for Shorts)
                new_sl = calculated_sl

        return new_sl

# ----------------- MACHINE LEARNING (Phase 18) -----------------
class MLValidator:
    def __init__(self, model_path="models/rf_validator.pkl"):
        self.model_path = model_path
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_trained = True
            logger.info("ML Model loaded from disk.")

    def _create_labels(self, df: pd.DataFrame, lookahead=5, atr_tp=2.0, atr_sl=1.0) -> pd.DataFrame:
        """Create Shifted Targets for Training (0 or 1) - Strict 'Hit TP before SL' Rule."""
        df['Target'] = 0

        # Shift iterators for lookahead window
        for i in range(len(df) - lookahead):
            current_close = df['Close'].iloc[i]
            current_atr = df['ATRr_14'].iloc[i]

            if pd.isna(current_atr):
                continue

            tp_price = current_close + (atr_tp * current_atr)
            sl_price = current_close - (atr_sl * current_atr)

            # Lookahead slice (future data)
            window = df.iloc[i+1 : i+1+lookahead]

            hit_tp = False
            for _, row in window.iterrows():
                # Did it hit SL first?
                if row['Low'] <= sl_price:
                    break # Loss
                # Did it hit TP?
                if row['High'] >= tp_price:
                    hit_tp = True
                    break # Win

            df.iat[i, df.columns.get_loc('Target')] = 1 if hit_tp else 0

        # Drop the last 'lookahead' rows because we can't label them
        df = df.iloc[:-lookahead].copy()
        df.dropna(inplace=True)
        return df

    def train(self, historical_df: pd.DataFrame):
        """Train Random Forest locally."""
        logger.info("Training Random Forest Classifier...")
        features = ['RSI_14', 'MACD_12_26_9', 'ATRr_14', 'Log_Return']

        # Ensure features exist
        missing = [f for f in features if f not in historical_df.columns]
        if missing:
            logger.warning(f"Missing features for ML Training: {missing}")
            return

        df_train = self._create_labels(historical_df.copy())

        X = df_train[features]
        y = df_train['Target']

        if len(X) < 100:
            logger.warning("Not enough data to train ML Model.")
            return

        self.model.fit(X, y)
        joblib.dump(self.model, self.model_path)
        self.is_trained = True
        logger.info("ML Model trained and saved.")

    def validate_signal(self, current_features: pd.DataFrame, direction: str) -> bool:
        """Returns True if Probability > 60%."""
        if not self.is_trained:
            return True # Pass if model not ready

        features = ['RSI_14', 'MACD_12_26_9', 'ATRr_14', 'Log_Return']
        X = current_features[features].iloc[-1:] # Get last row

        # predict_proba returns [prob_0, prob_1]
        probs = self.model.predict_proba(X)[0]

        # If direction is Long, we want prob_1 > 0.60
        # If direction is Short, we want prob_0 > 0.60
        threshold = 0.60

        if direction == "Long" and probs[1] > threshold:
            logger.info(f"ML Veto Passed: Long Probability {probs[1]:.2%}")
            return True
        elif direction == "Short" and probs[0] > threshold:
            logger.info(f"ML Veto Passed: Short Probability {probs[0]:.2%}")
            return True

        logger.warning(f"ML Veto Rejected: Probability {max(probs[0], probs[1]):.2%} for {direction}")
        return False
