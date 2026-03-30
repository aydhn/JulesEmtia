import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from logger import logger
import os
import joblib

class MLValidator:
    def __init__(self, model_path="models/rf_model.pkl"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info("RandomForest model loaded.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
                self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        else:
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def train(self, df: pd.DataFrame, target_col='Target'):
        # Phase 18: Train Model
        features = [col for col in df.columns if col not in ['Target', 'Close', 'Open', 'High', 'Low', 'Volume', 'Adj Close']]

        # Ensure we have data
        if df.empty or len(df) < 50:
            logger.warning("Not enough data to train model.")
            return

        # Create Target (1 if next 5 bars increase by 0.5%, 0 else) - Simplified example
        df['Target'] = np.where(df['Close'].shift(-5) > df['Close'] * 1.005, 1, 0)
        df.dropna(inplace=True)

        X = df[features]
        y = df['Target']

        # Train-test split strictly chronological to prevent lookahead
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        self.model.fit(X_train, y_train)
        score = self.model.score(X_test, y_test)
        logger.info(f"Model Retrained. Test Accuracy: {score:.2f}")

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def validate_signal(self, df: pd.DataFrame, direction: str, threshold=0.6) -> bool:
        # Phase 18: Probability Threshold Veto
        if not self.model or not hasattr(self.model, 'classes_'):
            return True # Allow if no trained model

        features = [col for col in df.columns if col not in ['Target', 'Close', 'Open', 'High', 'Low', 'Volume', 'Adj Close']]
        last_row = df[features].iloc[[-1]]

        try:
            proba = self.model.predict_proba(last_row)[0]
            # Assuming class 1 is positive outcome
            success_prob = proba[1]

            if direction == "Long" and success_prob < threshold:
                logger.info(f"ML Veto: Long rejected. Success probability {success_prob:.2f} < {threshold}")
                return False
            elif direction == "Short" and (1 - success_prob) < threshold: # Assuming class 0 is price drop success
                logger.info(f"ML Veto: Short rejected. Success probability {(1-success_prob):.2f} < {threshold}")
                return False

            return True
        except Exception as e:
             logger.error(f"ML Prediction Error: {e}")
             return True # Default to allow if error

ml_validator = MLValidator()