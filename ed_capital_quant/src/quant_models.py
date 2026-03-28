import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from joblib import dump, load
import os
import logging
from typing import Dict, Any, Tuple, Optional

from config import logger, MAX_OPEN_POSITIONS, MAX_CORRELATION_THRESHOLD, MAX_FRACTIONAL_KELLY_CAP, KELLY_MULTIPLIER

class MLValidator:
    """Uses Random Forest to validate technical signals based on historical probability."""
    def __init__(self, model_path: str = "models/rf_model.joblib"):
        self.model_path = model_path
        self.model = None
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = load(self.model_path)
                logger.info("Loaded ML validation model.")
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")

    def create_labels(self, df: pd.DataFrame, lookahead: int = 12, tp_pct: float = 0.02, sl_pct: float = 0.01) -> pd.DataFrame:
        """Labels data 1 (Success) if TP hits before SL within lookahead periods, else 0."""
        df['target'] = 0

        for i in range(len(df) - lookahead):
             current_close = df['close'].iloc[i]
             future_slice = df.iloc[i+1 : i+1+lookahead]

             # Calculate highs and lows relative to entry
             max_high = future_slice['high'].max()
             min_low = future_slice['low'].min()

             # Target hit (Long scenario)
             if max_high >= current_close * (1 + tp_pct) and min_low > current_close * (1 - sl_pct):
                 df.iloc[i, df.columns.get_loc('target')] = 1

             # Could also label Shorts differently or train two models,
             # For simplicity, treating high volatility breakouts as the positive class

        # Drop rows where we can't see the future
        df = df.iloc[:-lookahead]
        return df

    def train_model(self, data_dict: Dict[str, pd.DataFrame]):
        """Trains the Random Forest model on historical feature set."""
        logger.info("Starting ML Auto-Retraining...")
        all_features = []
        all_targets = []

        feature_cols = ['rsi_14_prev', 'macd_hist_prev', 'atr_14_prev', 'log_ret_prev']

        for ticker, df in data_dict.items():
            if df.empty or len(df) < 500:
                continue

            # Create labels avoiding lookahead bias during training
            labeled_df = self.create_labels(df.copy())
            labeled_df = labeled_df.dropna(subset=feature_cols + ['target'])

            if not labeled_df.empty:
                all_features.append(labeled_df[feature_cols])
                all_targets.append(labeled_df['target'])

        if not all_features:
            logger.warning("No data available for ML training.")
            return

        X = pd.concat(all_features, axis=0)
        y = pd.concat(all_targets, axis=0)

        if len(X) < 1000:
             logger.warning("Insufficient samples for robust ML training. Skipping.")
             return

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        # Train Random Forest
        rf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        rf.fit(X_train, y_train)

        score = rf.score(X_test, y_test)
        logger.info(f"ML Model Trained. Out-of-Sample Accuracy: {score:.2%}")

        dump(rf, self.model_path)
        self.model = rf

    def validate_signal(self, current_features: pd.Series, threshold: float = 0.60) -> bool:
        """Returns True if the probability of success is >= threshold."""
        if self.model is None:
            logger.warning("ML Model not loaded, bypassing ML validation.")
            return True # Bypass if no model

        feature_cols = ['rsi_14_prev', 'macd_hist_prev', 'atr_14_prev', 'log_ret_prev']

        # Ensure we have all required features
        for col in feature_cols:
            if col not in current_features:
                return False

        X = current_features[feature_cols].to_frame().T

        try:
             # predict_proba returns array of [prob_0, prob_1]
             proba = self.model.predict_proba(X)[0][1]

             if proba >= threshold:
                 logger.info(f"ML VALIDATION PASSED: Success probability {proba:.2%}")
                 return True
             else:
                 logger.warning(f"ML VETO: Success probability {proba:.2%} < {threshold:.2%}")
                 return False
        except Exception as e:
             logger.error(f"ML Validation failed: {e}")
             return False


class PortfolioManager:
    """Handles global risk exposure, correlation matrix vetoes, and Kelly Criterion."""
    def __init__(self, db_manager):
        self.db = db_manager
        self.correlation_matrix = None

    def update_correlation_matrix(self, close_prices: pd.DataFrame, window: int = 30):
        """Calculates rolling Pearson correlation matrix for the universe."""
        if close_prices.empty or len(close_prices) < window:
             return

        logger.info("Updating Dynamic Correlation Matrix...")
        # close_prices should be a DataFrame where columns are tickers and rows are dates
        recent_closes = close_prices.tail(window)

        # Calculate log returns for correlation
        returns = np.log(recent_closes / recent_closes.shift(1)).dropna()
        self.correlation_matrix = returns.corr()

    def check_correlation_veto(self, new_ticker: str, new_direction: str) -> bool:
        """Returns True if opening this trade violates correlation thresholds with existing trades."""
        if self.correlation_matrix is None or new_ticker not in self.correlation_matrix.columns:
            return False # Bypass if matrix not ready

        open_trades = self.db.get_open_trades()
        if open_trades.empty:
            return False

        for _, trade in open_trades.iterrows():
            existing_ticker = trade['ticker']
            existing_direction = trade['direction']

            if existing_ticker in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[new_ticker, existing_ticker]

                # If highly correlated (> 0.75) and same direction -> Veto
                if corr >= MAX_CORRELATION_THRESHOLD and new_direction == existing_direction:
                    logger.warning(f"CORRELATION VETO: {new_ticker} {new_direction} duplicates risk with open {existing_ticker} (Corr: {corr:.2f})")
                    return True

                # If highly negatively correlated (< -0.75) and opposite direction -> Veto (essentially same bet)
                if corr <= -MAX_CORRELATION_THRESHOLD and new_direction != existing_direction:
                    logger.warning(f"CORRELATION VETO: {new_ticker} {new_direction} duplicates risk with open {existing_ticker} (Corr: {corr:.2f})")
                    return True

        return False

    def check_global_limits(self) -> bool:
        """Returns True if the portfolio is at maximum capacity."""
        open_trades = self.db.get_open_trades()
        if len(open_trades) >= MAX_OPEN_POSITIONS:
            logger.warning(f"GLOBAL LIMIT VETO: Max open positions reached ({len(open_trades)}/{MAX_OPEN_POSITIONS})")
            return True
        return False

    def calculate_kelly_position_size(self, ticker: str, entry_price: float, sl_price: float) -> float:
        """Calculates Fractional Kelly Criterion position size."""
        # 1. Calculate Historical Performance from closed trades
        closed_trades = self.db.get_closed_trades()

        current_balance = self.db.get_balance()

        # Default fallback values if not enough history
        win_rate = 0.55
        avg_win = current_balance * 0.02
        avg_loss = current_balance * 0.01

        if not closed_trades.empty and len(closed_trades) >= 10:
             wins = closed_trades[closed_trades['net_pnl'] > 0]
             losses = closed_trades[closed_trades['net_pnl'] <= 0]

             win_rate = len(wins) / len(closed_trades)

             if not wins.empty:
                 avg_win = wins['net_pnl'].mean()
             if not losses.empty:
                 avg_loss = abs(losses['net_pnl'].mean())

        # 2. Apply Kelly Formula: f* = (bp - q) / b
        # where b is the ratio of avg_win to avg_loss (Profit Factor equivalent)
        # p is win_rate, q is loss_rate

        q = 1.0 - win_rate
        b = avg_win / avg_loss if avg_loss > 0 else 1.0

        kelly_fraction = 0.0
        if b > 0:
            kelly_fraction = (b * win_rate - q) / b

        # 3. Fractional Kelly & Cap Protections (JP Morgan Risk)
        # We use Half-Kelly or Quarter-Kelly to drastically reduce drawdown risk
        fractional_kelly = kelly_fraction * KELLY_MULTIPLIER

        if fractional_kelly <= 0:
            logger.warning(f"KELLY VETO: Negative Kelly fraction ({fractional_kelly:.4f}). System has lost edge.")
            # Fallback to minimal fixed risk if edge is temporarily lost but technicals align
            fractional_kelly = 0.005 # 0.5%

        # Hard Cap (Never risk more than MAX_FRACTIONAL_KELLY_CAP of total bankroll on one trade)
        risk_pct = min(fractional_kelly, MAX_FRACTIONAL_KELLY_CAP)

        # 4. Convert Risk % to Position Size (Lot)
        risk_amount = current_balance * risk_pct
        stop_distance = abs(entry_price - sl_price)

        if stop_distance == 0:
            logger.error("Stop distance is zero, cannot calculate position size.")
            return 0.0

        position_size = risk_amount / stop_distance

        logger.info(f"Kelly Calc: WinRate: {win_rate:.2%}, P/L Ratio (b): {b:.2f}, Kelly: {kelly_fraction:.2%}")
        logger.info(f"Fractional Risk Applied: {risk_pct:.2%} (${risk_amount:.2f}). Stop Distance: {stop_distance:.4f} -> Size: {position_size:.4f}")

        return position_size
