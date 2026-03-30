import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from logger import log
from config import MODEL_PATH

class MLValidator:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception as e:
                log.error(f"Error loading ML model: {e}")
        return None

    def train(self, df: pd.DataFrame):
        """
        Trains the Random Forest model to predict trade success.
        df should contain historical features and a 'Target' column (1 for Win, 0 for Loss).
        """
        if 'Target' not in df.columns:
            log.warning("No 'Target' column found for training.")
            return False

        features = df.drop(columns=['Target', 'time', 'Close', 'High', 'Low', 'Open', 'Volume'], errors='ignore')
        target = df['Target']

        # Drop NaNs
        valid_idx = features.dropna().index
        features = features.loc[valid_idx]
        target = target.loc[valid_idx]

        if len(features) < 100:
            log.warning("Not enough data to train ML model.")
            return False

        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        self.model.fit(features, target)

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)
        log.info(f"ML Model trained and saved to {self.model_path}")
        return True

    def validate_signal(self, current_features: pd.Series, threshold: float = 0.55) -> bool:
        """
        Returns True if the ML model predicts a win probability > threshold.
        """
        if self.model is None:
            log.warning("ML Model not loaded. Skipping ML validation.")
            return True # Default to True if no model exists yet

        try:
            # Format series for prediction
            features = pd.DataFrame([current_features]).drop(columns=['time', 'Close', 'High', 'Low', 'Open', 'Volume', 'HTF_Close'], errors='ignore')
            features = features.fillna(0) # Basic imputation

            # Predict probability of class 1 (Win)
            prob_win = self.model.predict_proba(features)[0][1]

            if prob_win >= threshold:
                log.info(f"ML Validator: Signal APPROVED (Prob: {prob_win:.2f})")
                return True
            else:
                log.warning(f"ML Validator: Signal REJECTED (Prob: {prob_win:.2f} < {threshold})")
                return False
        except Exception as e:
            log.error(f"ML Validation Error: {e}")
            return True # Default to True on error to not block system
