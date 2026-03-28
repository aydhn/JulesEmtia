import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
from core.logger import setup_logger
from core.config import DATA_DIR

logger = setup_logger("ml_validator")

class MLValidator:
    """
    Random Forest Classifier to validate technical signals based on historical success.
    Protects against overfitting with simple depth constraints.
    """
    def __init__(self):
        self.model_path = os.path.join(DATA_DIR, "rf_model.joblib")
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=5, # Keep it shallow to prevent overfitting
            random_state=42,
            n_jobs=-1 # Use all CPU cores
        )
        self.is_trained = False
        self.threshold = 0.55 # 55% probability required to validate

        # Load model if exists
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                self.is_trained = True
                logger.info("Loaded pre-trained Random Forest model.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")

    def create_labels(self, df: pd.DataFrame, horizon: int = 10, tp_atr_mult: float = 2.0, sl_atr_mult: float = 1.0) -> pd.DataFrame:
        """
        Labeling function: 1 if successful, 0 if failure within 'horizon' bars.
        Simulates if a hypothetical trade hit TP before SL.
        """
        # This is simplified for speed. A true labeling function would simulate the exact trailing stop.
        df['target_return'] = df['close'].shift(-horizon) / df['close'] - 1.0

        # Approximate: if return > TP threshold based on current ATR
        # We need a percentage representation of ATR
        df['atr_pct'] = df['atr_14'] / df['close']

        # Successful Long if it reaches TP
        df['label'] = np.where(df['target_return'] > (df['atr_pct'] * tp_atr_mult), 1, 0)

        # Drop rows where target_return is NaN (end of dataset)
        df.dropna(subset=['target_return'], inplace=True)
        return df

    def train(self, historical_data: dict):
        """
        Trains the model on the provided historical MTF dataset.
        historical_data is a dict mapping ticker to (htf_df, ltf_df).
        """
        logger.info("Training Random Forest ML Validator...")

        features_list = []
        labels_list = []

        # Features to use (shifted indicators to avoid lookahead bias during training!)
        feature_cols = ['ema_50_prev', 'ema_200_prev', 'rsi_14_prev', 'MACDh_12_26_9_prev', 'log_return']

        for ticker, (htf_df, ltf_df) in historical_data.items():
            if ltf_df is None or ltf_df.empty:
                continue

            # Assume ltf_df already has features added
            df_labeled = self.create_labels(ltf_df.copy())

            # Extract features and labels
            # Ensure no NaNs
            valid_rows = df_labeled.dropna(subset=feature_cols + ['label'])

            features_list.append(valid_rows[feature_cols])
            labels_list.append(valid_rows['label'])

        if not features_list:
            logger.warning("No valid data for ML training.")
            return

        X = pd.concat(features_list)
        y = pd.concat(labels_list)

        if len(X) < 1000:
            logger.warning(f"Insufficient data for ML training ({len(X)} rows). Need at least 1000.")
            return

        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train)
        accuracy = self.model.score(X_test, y_test)

        logger.info(f"ML Model trained successfully. Out-of-Sample Accuracy: {accuracy:.2%}")

        # Save model
        joblib.dump(self.model, self.model_path)
        self.is_trained = True

    def validate_signal(self, current_features: pd.DataFrame) -> bool:
        """
        Predicts the probability of success for the current signal.
        """
        if not self.is_trained:
            # If not trained, we don't veto.
            return True

        feature_cols = ['ema_50_prev', 'ema_200_prev', 'rsi_14_prev', 'MACDh_12_26_9_prev', 'log_return']

        # Extract the latest row's features
        X_current = current_features[feature_cols].iloc[-1:].values

        # Predict probability of class 1 (Success)
        prob = self.model.predict_proba(X_current)[0][1]

        if prob >= self.threshold:
            logger.info(f"ML Validation PASSED: Success Probability {prob:.2%}")
            return True
        else:
            logger.warning(f"ML Validation FAILED: Success Probability {prob:.2%} < {self.threshold:.2%}")
            return False
