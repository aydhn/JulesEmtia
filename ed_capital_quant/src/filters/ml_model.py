import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from src.core.logger import logger
from src.core.config import ML_PROB_THRESHOLD

MODEL_PATH = "data/rf_model.pkl"

class MLValidator:
    def __init__(self):
        self.model = None
        self.threshold = ML_PROB_THRESHOLD
        self.load_model()

    def load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                logger.info("ML Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load ML model: {e}")
                self.model = None
        else:
            logger.warning("No trained ML model found. Auto-veto disabled.")

    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Selects columns that are used as features for the Random Forest model.
        """
        # Example features, adjust based on your generated feature names
        features = [col for col in df.columns if any(indicator in col for indicator in ['RSI', 'MACD', 'ATR', 'EMA', 'BBL', 'BBU', 'Log_Return'])]
        return df[features]

    def create_labels(self, df: pd.DataFrame, horizon: int = 10, profit_target: float = 0.02) -> pd.Series:
        """
        Creates target labels for training.
        1 if price moves favorably (>= target in absolute terms) within 'horizon' bars, 0 otherwise.
        """
        # Shift close prices forward to peek into future (ONLY FOR TRAINING LABELS)
        future_returns = df['Close'].shift(-horizon) / df['Close'] - 1
        # Predict if the absolute move is greater than the target (volatility/breakout)
        labels = np.where(abs(future_returns) >= profit_target, 1, 0)
        return pd.Series(labels, index=df.index)

    def train(self, data: pd.DataFrame):
        logger.info("Training Random Forest Classifier...")

        df = data.copy()
        features = self.extract_features(df)
        labels = self.create_labels(df)

        # Drop NaN rows caused by shifting/indicators
        valid_idx = features.notna().all(axis=1) & labels.notna()
        X = features[valid_idx]
        y = labels[valid_idx]

        if len(X) < 100:
            logger.warning("Not enough data to train ML model.")
            return False

        # Train model
        self.model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
        self.model.fit(X, y)

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        logger.info(f"Model trained and saved to {MODEL_PATH}")
        return True

    def validate_signal(self, current_row: pd.Series) -> bool:
        """
        Returns True if the ML model predicts success probability >= threshold.
        """
        if self.model is None:
            return True # Fallback to technicals if no model

        try:
            # Extract features matching the training set
            # Current row is a Series, reshape to (1, -1) DataFrame
            features = self.extract_features(pd.DataFrame([current_row]))

            # Predict probability of class 1 (Success)
            prob = self.model.predict_proba(features)[0][1]
            logger.debug(f"ML Success Probability: {prob:.2f}")

            if prob >= self.threshold:
                return True
            else:
                logger.info(f"ML Veto: Signal probability {prob:.2f} < {self.threshold}")
                return False
        except Exception as e:
            logger.error(f"ML Validation error: {e}")
            return True # Do not block if ML fails unexpectedly

if __name__ == "__main__":
    validator = MLValidator()
