import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
import asyncio
from typing import Tuple, Optional
from logger import logger

class MLValidator:
    """
    Phase 18: Machine Learning Signal Validation
    Uses RandomForest to validate technical signals.
    Trains locally (zero-budget) to prevent curve-fitting and false positives.
    """

    MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'rf_model.pkl')

    # Feature columns expected by the model
    FEATURES = [
        'RSI_14', 'MACD', 'MACD_Hist', 'MACD_Signal',
        'ATR_14', 'Z_Score_50', 'Log_Return', 'Prev_Return'
    ]

    @classmethod
    def _create_labels(cls, df: pd.DataFrame, forward_periods: int = 5, profit_threshold: float = 0.005) -> pd.DataFrame:
        """
        Creates binary target variable (y) for training.
        1: Price increased by > profit_threshold in next 'N' periods (Successful Long)
        0: Failed or went down.
        Zero Lookahead Bias: Target is strictly based on future returns shifted backward.
        """
        df = df.copy()

        # Calculate future return (forward-looking strictly for labeling training data)
        df['Future_Return'] = df['Close'].shift(-forward_periods) / df['Close'] - 1

        # Labeling rules: 1 if hit target, 0 otherwise
        df['Target'] = np.where(df['Future_Return'] > profit_threshold, 1, 0)

        # Drop NaN targets (the last N rows)
        df.dropna(subset=['Target'], inplace=True)
        return df

    @classmethod
    def train_model(cls, historical_data: dict[str, pd.DataFrame]) -> None:
        """
        Trains RandomForest using aggregated historical data from multiple tickers.
        """
        logger.info("Starting ML model training...")

        all_features = []
        all_targets = []

        for ticker, data in historical_data.items():
            if data is None or data.empty:
                continue

            labeled_data = cls._create_labels(data)

            # Select features and targets
            X = labeled_data[cls.FEATURES]
            y = labeled_data['Target']

            all_features.append(X)
            all_targets.append(y)

        if not all_features:
            logger.warning("No data available for ML training.")
            return

        # Combine all tickers into a single training set
        X_train = pd.concat(all_features, axis=0)
        y_train = pd.concat(all_targets, axis=0)

        # Clean NaNs and infinite values
        X_train.replace([np.inf, -np.inf], np.nan, inplace=True)
        valid_idx = X_train.dropna().index
        X_train = X_train.loc[valid_idx]
        y_train = y_train.loc[valid_idx]

        logger.info(f"Training RandomForest with {len(X_train)} samples across universe.")

        # Initialize and Train Model
        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,       # Shallow depth to prevent overfitting
            min_samples_leaf=20,
            random_state=42,
            n_jobs=-1          # Use all CPU cores
        )

        clf.fit(X_train, y_train)

        # Save model locally (Joblib is efficient for NumPy arrays)
        joblib.dump(clf, cls.MODEL_PATH)
        logger.info(f"ML Model trained and saved to {cls.MODEL_PATH}.")

    @classmethod
    async def async_train_model(cls, historical_data: dict[str, pd.DataFrame]) -> None:
        """Asynchronous wrapper for scheduled weekend retraining."""
        await asyncio.to_thread(cls.train_model, historical_data)

    @classmethod
    def validate_signal(cls, current_features: pd.Series, threshold: float = 0.60) -> Tuple[bool, float]:
        """
        Validates a technical signal using the trained ML model.
        Returns (is_approved, probability).
        """
        try:
            if not os.path.exists(cls.MODEL_PATH):
                logger.warning("ML Model not found! Bypassing ML Validation.")
                return True, 0.5

            clf = joblib.load(cls.MODEL_PATH)

            # Extract relevant features
            X_current = current_features[cls.FEATURES].to_frame().T
            X_current.replace([np.inf, -np.inf], np.nan, inplace=True)
            X_current.fillna(0, inplace=True) # Handle missing

            # Predict Probability of Success (Class 1)
            prob_success = clf.predict_proba(X_current)[0][1]

            is_approved = prob_success >= threshold

            if not is_approved:
                logger.warning(f"ML Veto: Signal rejected. Probability {prob_success:.2f} < {threshold}.")
            else:
                logger.info(f"ML Approval: Signal probability {prob_success:.2f} >= {threshold}.")

            return is_approved, prob_success

        except Exception as e:
            logger.error(f"Error during ML signal validation: {e}")
            return True, 0.5 # Fail-open in case of error
