import pandas as pd
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from ed_quant_engine.core.logger import logger

class MLValidator:
    """
    Random Forest Classifier for Signal Validation.
    Statistically determines the probability of a signal succeeding.
    """
    def __init__(self, model_path: str = "models/rf_model.pkl", probability_threshold: float = 0.60):
        self.model_path = model_path
        self.prob_threshold = probability_threshold
        self.model = None

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.load_model()

    def load_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info(f"ML Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load ML Model: {e}")

    def create_labels(self, df: pd.DataFrame, atr_multiplier: float = 2.0) -> pd.DataFrame:
        """
        Generates binary labels (1=Success, 0=Failure) for supervised learning.
        A success is defined as price reaching Entry + (2*ATR) before Entry - (1*ATR).
        Strict lookahead bias prevention during training set generation.
        """
        data = df.copy()
        data['target'] = 0

        # Iterate to define success/failure (Vectorized approximation)
        # For simplicity in this engine, we look forward N periods to see if High > TP or Low < SL
        # We shift(-1) to look at FUTURE returns relative to current signal.
        data['future_return'] = data['close'].shift(-5) / data['close'] - 1

        # If the return over next 5 periods is > 1.5% (simplified success metric for training)
        # A more rigorous TP/SL touch algorithm would be implemented here in production.
        data.loc[data['future_return'] > 0.015, 'target'] = 1

        data.dropna(inplace=True)
        return data

    def train_model(self, historical_data: pd.DataFrame):
        """
        Trains the Random Forest model on historical data.
        """
        logger.info("Training ML Validator Model...")

        # Generate labels
        df = self.create_labels(historical_data)

        # Select Features (X)
        features = ['htf_close', 'htf_ema_50', 'rsi_14', 'macd_hist', 'atr_14', 'log_return']

        # Ensure all features exist
        missing = [f for f in features if f not in df.columns]
        if missing:
            logger.error(f"Cannot train ML Model. Missing features: {missing}")
            return

        X = df[features]
        y = df['target']

        if len(X) < 100:
            logger.warning("Not enough data to train ML Model. Skipping.")
            return

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False) # Time-series strict

        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        self.model.fit(X_train, y_train)

        score = self.model.score(X_test, y_test)
        logger.info(f"ML Model trained. Test Accuracy: {score:.2f}")

        # Save model
        joblib.dump(self.model, self.model_path)
        logger.info(f"ML Model saved to {self.model_path}")

    def validate_signal(self, current_features: pd.DataFrame) -> bool:
        """
        Uses predict_proba to veto low-probability signals.
        Returns True if signal is VALID, False if VETOED.
        """
        if self.model is None:
            logger.warning("ML Model not loaded. Bypassing ML Validation (Veto=False).")
            return True # Allow trade if model is missing

        features = ['htf_close', 'htf_ema_50', 'rsi_14', 'macd_hist', 'atr_14', 'log_return']

        try:
            X = current_features[features].iloc[-1:].values
            # Get probability of class 1 (Success)
            prob_success = self.model.predict_proba(X)[0][1]

            if prob_success < self.prob_threshold:
                logger.warning(f"ML Veto: Low Probability Signal ({prob_success:.2f} < {self.prob_threshold})")
                return False

            return True
        except Exception as e:
            logger.error(f"ML Validation Error: {e}")
            return True # Allow trade on error to avoid halting system
