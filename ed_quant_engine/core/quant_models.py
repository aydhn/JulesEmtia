import pandas as pd
import pandas_ta as ta
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from typing import Tuple

from .infrastructure import logger, PaperDB
from .config import SPREADS, MAX_RISK_PER_TRADE, GLOBAL_EXPOSURE_LIMIT, TICKERS

# ----------------- TECHNICAL INDICATORS (Phase 3) -----------------
def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add MTF indicators using vectorized pandas_ta operations."""
    if len(df) < 200:
        logger.warning(f"Dataframe too short ({len(df)}) for features.")
        return df

    # Trend Filter (EMA 50 & 200)
    df.ta.ema(length=50, append=True)
    df.ta.ema(length=200, append=True)

    # Momentum & RSI
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3, append=True)

    # ADX Trend Strength
    df.ta.adx(length=14, append=True)

    # Volatility & Risk (ATR & BBands)
    df.ta.atr(length=14, append=True)
    df.ta.bbands(length=20, std=2, append=True)

    # Micro Flash Crash Detection (Phase 19 Z-Score)
    sma = df['Close'].rolling(window=20).mean()
    std = df['Close'].rolling(window=20).std()
    df['Z_Score'] = (df['Close'] - sma) / std

    # Price Action (Log Returns)
    df['Log_Return'] = np.log(df['Close'] / df['Close'].shift(1))

    # Uyumsuzluk (Divergence) Detection (Price vs RSI)
    # Check if price makes lower low, but RSI makes higher low
    df['Price_Min'] = df['Low'].rolling(window=5, center=True).min()
    df['Price_Max'] = df['High'].rolling(window=5, center=True).max()

    if 'RSI_14' in df.columns:
        df['RSI_Min'] = df['RSI_14'].rolling(window=5, center=True).min()
        df['RSI_Max'] = df['RSI_14'].rolling(window=5, center=True).max()

        price_diff = df['Close'].diff(periods=10)
        rsi_diff = df['RSI_14'].diff(periods=10)

        df['Bullish_Div'] = (price_diff < 0) & (rsi_diff > 0) & (df['RSI_14'] < 40)
        df['Bearish_Div'] = (price_diff > 0) & (rsi_diff < 0) & (df['RSI_14'] > 60)

    df.dropna(inplace=True)
    return df

# ----------------- RISK & EXECUTION (Phases 11, 12, 15, 21) -----------------
class RiskManager:
    def __init__(self, db: PaperDB):
        self.db = db

    def calculate_kelly_fraction(self) -> float:
        closed_trades = self.db.get_closed_trades()
        if len(closed_trades) < 10:
            return 0.01

        recent_trades = closed_trades.tail(50)
        wins = recent_trades[recent_trades['pnl'] > 0]
        losses = recent_trades[recent_trades['pnl'] <= 0]

        if len(wins) == 0:
            return 0.0

        p = len(wins) / len(recent_trades)
        q = 1.0 - p

        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 1.0
        b = avg_win / avg_loss

        if b == 0:
            return 0.0

        f_star = (b * p - q) / b
        fractional_kelly = f_star / 2.0
        safe_kelly = max(0.005, min(fractional_kelly, MAX_RISK_PER_TRADE))
        logger.info(f"Dynamic Kelly Calculated: p={p:.2f}, b={b:.2f} -> Risk: {safe_kelly:.2%}")
        return safe_kelly

    def calculate_position_size(self, current_price: float, atr: float, balance: float) -> float:
        risk_pct = self.calculate_kelly_fraction()
        risk_amount = balance * risk_pct
        stop_distance = 1.5 * atr

        if stop_distance <= 0:
            return 0.0

        lot_size = risk_amount / stop_distance
        return round(lot_size, 4)

    def dynamic_spread_slippage(self, ticker: str, current_price: float, atr: float) -> Tuple[float, float]:
        category = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")
        base_spread = SPREADS.get(category, 0.001)

        volatility_factor = (atr / current_price) / 0.005
        volatility_factor = max(1.0, min(volatility_factor, 3.0))

        slippage = (base_spread * 0.5) * volatility_factor
        return base_spread, slippage

    def check_portfolio_limits(self, new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame) -> bool:
        open_trades = self.db.get_open_trades()

        if len(open_trades) >= GLOBAL_EXPOSURE_LIMIT:
            logger.warning("Global Exposure Limit Reached. Rejecting new signal.")
            return False

        for _, trade in open_trades.iterrows():
            existing_ticker = trade['ticker']
            existing_dir = trade['direction']

            if existing_ticker == new_ticker and existing_dir == new_direction:
                return False

            if new_ticker in corr_matrix.columns and existing_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, existing_ticker]
                if corr > 0.75 and new_direction == existing_dir:
                    logger.warning(f"Correlation Veto: {new_ticker} vs {existing_ticker} (Corr: {corr:.2f})")
                    return False
        return True

    def calculate_trailing_stop(self, direction: str, current_price: float, entry_price: float, current_sl: float, atr: float) -> float:
        new_sl = current_sl

        if direction == "Long":
            if current_price >= entry_price + (1.0 * atr):
                if current_sl < entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")
            calculated_sl = current_price - (1.5 * atr)
            if calculated_sl > new_sl:
                new_sl = calculated_sl
        elif direction == "Short":
            if current_price <= entry_price - (1.0 * atr):
                if current_sl > entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")
            calculated_sl = current_price + (1.5 * atr)
            if calculated_sl < new_sl:
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
        df['Target'] = 0
        for i in range(len(df) - lookahead):
            current_close = df['Close'].iloc[i]
            current_atr = df['ATRr_14'].iloc[i]
            if pd.isna(current_atr): continue

            tp_price = current_close + (atr_tp * current_atr)
            sl_price = current_close - (atr_sl * current_atr)
            window = df.iloc[i+1 : i+1+lookahead]
            hit_tp = False
            for _, row in window.iterrows():
                if row['Low'] <= sl_price: break
                if row['High'] >= tp_price:
                    hit_tp = True
                    break
            df.iat[i, df.columns.get_loc('Target')] = 1 if hit_tp else 0
        df = df.iloc[:-lookahead].copy()
        df.dropna(inplace=True)
        return df

    def train(self, historical_df: pd.DataFrame):
        logger.info("Training Random Forest Classifier...")
        features = ['RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return', 'ADX_14']
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
        if not self.is_trained: return True

        features = ['RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return', 'ADX_14']
        if any(f not in current_features.columns for f in features):
            return True

        X = current_features[features].iloc[-1:]
        probs = self.model.predict_proba(X)[0]
        threshold = 0.60

        if direction == "LONG" and probs[1] > threshold:
            logger.info(f"ML Veto Passed: Long Probability {probs[1]:.2%}")
            return True
        elif direction == "SHORT" and probs[0] > threshold:
            logger.info(f"ML Veto Passed: Short Probability {probs[0]:.2%}")
            return True

        logger.warning(f"ML Veto Rejected: Probability {max(probs[0], probs[1]):.2%} for {direction}")
        return False
