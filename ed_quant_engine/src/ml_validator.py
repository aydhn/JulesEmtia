import pandas as pd
import numpy as np
import logging
import os
import joblib
from sklearn.ensemble import RandomForestClassifier

logger = logging.getLogger(__name__)

class MLValidator:
    """
    Phase 18: Random Forest Classifier for Signal Validation & Auto-Retraining
    """
    def __init__(self, model_path: str = "models/rf_model.pkl", probability_threshold: float = 0.60):
        self.model_path = model_path
        self.probability_threshold = probability_threshold
        self.model = self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception as e:
                logger.warning(f"Failed to load ML model: {e}")

        # Initialize a new robust RF model if not exists
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            min_samples_split=10,
            random_state=42,
            n_jobs=-1
        )

    def _create_labels(self, df: pd.DataFrame, lookforward: int = 10, profit_target: float = 0.02) -> pd.DataFrame:
        """Labels historical data: 1 if hit profit target before stop, 0 otherwise."""
        df = df.copy()
        df['Target_Met'] = 0

        # Vectorized check for future highest/lowest
        future_highs = df['High'].shift(-lookforward).rolling(window=lookforward, min_periods=1).max()
        future_lows = df['Low'].shift(-lookforward).rolling(window=lookforward, min_periods=1).min()

        long_success = future_highs >= df['Close'] * (1 + profit_target)
        short_success = future_lows <= df['Close'] * (1 - profit_target)

        # Naive labeling for training purposes
        df.loc[long_success | short_success, 'Target_Met'] = 1

        return df.dropna()

    def train(self, all_data: pd.DataFrame):
        """Phase 18: Otonom Yeniden Eğitim (Auto-Retraining)."""
        logger.info("Starting ML Retraining...")
        try:
            labeled_data = self._create_labels(all_data)

            # Select feature columns (exclude dates, targets, open/high/low etc)
            feature_cols = [c for c in labeled_data.columns if c not in ['Open', 'High', 'Low', 'Close', 'Volume', 'Date', 'Target_Met'] and not c.startswith('Bullish') and not c.startswith('Bearish')]

            X = labeled_data[feature_cols].fillna(0)
            y = labeled_data['Target_Met']

            if len(X) < 100:
                logger.warning("Not enough data to train ML model.")
                return

            self.model.fit(X, y)

            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info("ML Model successfully retrained and saved.")
        except Exception as e:
            logger.error(f"ML Training failed: {e}")

    def validate_signal(self, current_features: pd.DataFrame, direction: str) -> bool:
        """Validates if the signal has a high probability of success."""
        if not hasattr(self.model, "classes_"):
            # Model not trained yet, pass-through
            return True

        try:
            feature_cols = [c for c in current_features.columns if c not in ['Open', 'High', 'Low', 'Close', 'Volume', 'Date', 'Target_Met'] and not c.startswith('Bullish') and not c.startswith('Bearish')]

            X_curr = current_features.iloc[-1:][feature_cols].fillna(0)

            # Use align to handle missing feature columns by filling with 0 (helps if feature set changed slightly)
            if hasattr(self.model, "feature_names_in_"):
                expected_cols = self.model.feature_names_in_
                for col in expected_cols:
                    if col not in X_curr.columns:
                        X_curr[col] = 0.0
                X_curr = X_curr[expected_cols]

            prob = self.model.predict_proba(X_curr)[0]
            # Assuming class 1 is success
            success_prob = prob[1] if len(prob) > 1 else prob[0]

            if success_prob < self.probability_threshold:
                logger.warning(f"ML Veto! Signal success probability ({success_prob:.2f}) below threshold.")
                return False

            logger.info(f"ML Validation Passed (Prob: {success_prob:.2f})")
            return True

        except Exception as e:
            logger.error(f"ML Validation error: {e}")
            return True # Fail-safe, don't block if ML errors out
