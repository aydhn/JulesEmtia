import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from src.features import add_features
from src.data_loader import DataLoader
from src.config import MODELS_PATH
import joblib
import os
from src.logger import logger

class MLValidator:
    def __init__(self, model_filename: str = "rf_model.pkl", threshold: float = 0.60):
        self.model_path = os.path.join(MODELS_PATH, model_filename)
        self.threshold = threshold
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded ML model from {self.model_path}")
            else:
                logger.warning("No ML model found. It needs to be trained.")
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")

    def create_labels(self, df: pd.DataFrame, lookforward: int = 5, profit_target: float = 0.01) -> pd.DataFrame:
        """
        Creates binary labels (1=Success, 0=Failure) based on future returns.
        Avoids lookahead bias by shifting returns backwards.
        """
        # Feature Engineering columns assumed present
        # Target: Did the price go up by 'profit_target' % in the next 'lookforward' bars?
        df['Target'] = (df['Close'].shift(-lookforward) / df['Close'] - 1) > profit_target
        df['Target'] = df['Target'].astype(int)

        # Drop NaN targets (the last 'lookforward' bars)
        df = df.dropna(subset=['Target'])
        return df

    def prepare_data(self, df: pd.DataFrame) -> tuple:
        """
        Prepares X (features) and y (target) for training.
        """
        df = self.create_labels(df.copy())

        # Select Features (Ensure no future data is here!)
        features = ['EMA_50', 'EMA_200', 'RSI_14', 'MACD', 'MACD_Hist', 'ATR_14', 'Log_Return']

        # Keep only rows where all features are available
        df = df.dropna(subset=features)

        X = df[features]
        y = df['Target']
        return X, y

    def train_model(self, data: dict):
        """
        Trains the RandomForestClassifier using historical data from multiple tickers.
        """
        logger.info("Starting ML model training...")
        all_X = []
        all_y = []

        for ticker, df in data.items():
            if df.empty or len(df) < 200: continue
            df = add_features(df.copy())
            X, y = self.prepare_data(df)
            if not X.empty:
                all_X.append(X)
                all_y.append(y)

        if not all_X:
            logger.warning("No valid data to train ML model.")
            return

        X_combined = pd.concat(all_X)
        y_combined = pd.concat(all_y)

        # Train/Test Split (Time-series aware split is better, but this is a simplified example)
        # Using a standard split for now to keep CPU usage low. In production, use TimeSeriesSplit.
        X_train, X_test, y_train, y_test = train_test_split(X_combined, y_combined, test_size=0.2, shuffle=False)

        # RandomForest parameters tuned for speed/avoiding overfitting
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)

        # Evaluate (Optional)
        score = clf.score(X_test, y_test)
        logger.info(f"ML Model trained. Test Accuracy: {score:.2f}")

        # Save model
        joblib.dump(clf, self.model_path)
        self.model = clf
        logger.info(f"Model saved to {self.model_path}")

    def validate_signal(self, current_features: dict) -> bool:
        """
        Predicts the probability of success for a given set of features.
        Returns True if probability >= threshold.
        """
        if self.model is None:
            logger.warning("ML Model not loaded. Skipping ML validation (returning True).")
            return True # Fail-open if no model

        # Ensure features are in the correct order
        feature_cols = ['EMA_50', 'EMA_200', 'RSI_14', 'MACD', 'MACD_Hist', 'ATR_14', 'Log_Return']
        try:
            # Create a 2D array (1 sample, n features)
            X_input = np.array([current_features[col] for col in feature_cols]).reshape(1, -1)

            # predict_proba returns [[prob_class_0, prob_class_1]]
            prob_success = self.model.predict_proba(X_input)[0][1]

            if prob_success >= self.threshold:
                logger.info(f"ML Validation Passed (Prob: {prob_success:.2f})")
                return True
            else:
                 logger.info(f"ML Veto: Rejected signal (Prob: {prob_success:.2f} < {self.threshold})")
                 return False

        except Exception as e:
            logger.error(f"Error during ML validation: {e}. Passing signal.")
            return True # Fail-open on error

