import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from src.logger import get_logger

logger = get_logger("ml_validator")
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "rf_validator.joblib")
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

def create_labels(df: pd.DataFrame, forward_period: int = 12) -> pd.DataFrame:
    """Creates binary labels indicating if a trade would be successful within N future periods."""
    if df.empty: return df

    df_labels = df.copy()

    # Look ahead strictly for training labels (NEVER used in inference)
    df_labels['Future_Return'] = df_labels['Close'].shift(-forward_period) / df_labels['Close'] - 1.0

    # Label 1 if return > ATR threshold (approximate success), else 0
    # A robust implementation would simulate actual SL/TP hits row-by-row.
    df_labels['Target'] = np.where(df_labels['Future_Return'] > 0.005, 1, 0)

    # Drop rows where we can't look ahead yet
    df_labels.dropna(subset=['Target'], inplace=True)
    return df_labels

def train_model(df_features: pd.DataFrame) -> bool:
    """Trains a Random Forest classifier to predict trade success."""
    try:
        df = create_labels(df_features)

        # Features to use
        features = ['RSI_14', 'MACD', 'MACD_Hist', 'ATR_14', 'Log_Return', 'Pct_Change']

        X = df[features].dropna()
        y = df.loc[X.index, 'Target']

        if len(X) < 500:
            logger.warning("Insufficient data to train ML model (<500 samples).")
            return False

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False) # Important: Time-series split (no shuffle)

        # Train RF
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        clf.fit(X_train, y_train)

        score = clf.score(X_test, y_test)
        logger.info(f"ML Model trained successfully. Test Accuracy: {score:.2f}")

        # Save model
        joblib.dump(clf, MODEL_PATH)
        return True

    except Exception as e:
        logger.error(f"Error training ML model: {e}")
        return False

def check_ml_veto(features_dict: dict, threshold: float = 0.60) -> bool:
    """Returns True if the ML model predicts a low probability of success (<60%)."""
    if not os.path.exists(MODEL_PATH):
        logger.warning("ML Model not found. Skipping validation.")
        return False # Fail open if no model

    try:
        clf = joblib.load(MODEL_PATH)

        # Order must match training features
        X_infer = pd.DataFrame([{
            'RSI_14': features_dict.get('RSI_14', 50),
            'MACD': features_dict.get('MACD', 0),
            'MACD_Hist': features_dict.get('MACD_Hist', 0),
            'ATR_14': features_dict.get('ATR_14', 0),
            'Log_Return': features_dict.get('Log_Return', 0),
            'Pct_Change': features_dict.get('Pct_Change', 0)
        }])

        # Get probability of class 1 (Success)
        prob_success = clf.predict_proba(X_infer)[0][1]

        if prob_success < threshold:
            logger.info(f"ML Veto: Trade probability {prob_success:.2f} < {threshold:.2f} threshold.")
            return True

        logger.debug(f"ML Approved trade. Probability: {prob_success:.2f}")
        return False

    except Exception as e:
        logger.error(f"Error during ML inference: {e}")
        return False
