import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config

logger = setup_logger("MLValidator")

class MLValidator:
    def __init__(self, model_path=Config.MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            logger.info("RandomForest Model loaded successfully.")
        else:
            logger.warning("No pre-trained model found. Needs training.")
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def create_labels(self, df: pd.DataFrame, n_periods=10, sl_multiplier=1.5, tp_multiplier=3.0) -> pd.DataFrame:
        """Labels historical data for training (1=Hit TP before SL, 0=Hit SL or timeout)."""
        df = df.copy()
        df['Target'] = 0

        # Simplified vectorized labeling logic (mockup for performance)
        # Real implementation requires forward-looking iteration carefully avoiding lookahead bias during training
        future_returns = df['Close'].shift(-n_periods) / df['Close'] - 1
        df['Target'] = np.where(future_returns > (df['ATR_14'] * tp_multiplier / df['Close']), 1, 0)

        df.dropna(inplace=True)
        return df

    def train(self, df: pd.DataFrame):
        """Trains the Random Forest model and saves it."""
        try:
            df_labeled = self.create_labels(df)
            features = ['EMA_50', 'RSI_14', 'MACD', 'ATR_14', 'Returns']

            X = df_labeled[features]
            y = df_labeled['Target']

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            self.model.fit(X_train, y_train)
            score = self.model.score(X_test, y_test)

            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)

            logger.info(f"Model trained with accuracy: {score:.2f} and saved.")
        except Exception as e:
            logger.error(f"Error training ML model: {e}")

    def validate_signal(self, current_features: dict, threshold=0.60) -> bool:
        """Validates a strategy signal. Returns True if probability > threshold."""
        if self.model is None:
             logger.warning("Model not loaded, skipping ML validation.")
             return True # Pass-through if no model

        try:
            # Reconstruct feature array
            X_curr = np.array([[
                current_features.get('EMA_50', 0),
                current_features.get('RSI_14', 50),
                current_features.get('MACD', 0),
                current_features.get('ATR_14', 0),
                current_features.get('Returns', 0)
            ]])

            prob = self.model.predict_proba(X_curr)[0][1] # Prob of class 1

            if prob >= threshold:
                 logger.info(f"ML Validation Passed: {prob:.2f} probability.")
                 return True
            else:
                 logger.warning(f"ML Veto: Low Probability ({prob:.2f})")
                 return False

        except Exception as e:
            logger.error(f"Error during ML validation: {e}")
            return False # Veto on error for safety
