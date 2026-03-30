import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from typing import Tuple

from logger import log
from features import add_features
from data_loader import _download_yf_data, UNIVERSE

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'rf_model.joblib')

def _create_labels(df: pd.DataFrame, target_return: float = 0.02, stop_loss: float = -0.01, lookforward: int = 10) -> pd.DataFrame:
    """
    Creates target labels for the classification model (1 = Success, 0 = Failure).
    Checks if the price hits target_return before stop_loss within the next N periods.
    """
    df = df.copy()
    labels = []

    # Iterate to simulate future paths. Avoid lookahead by shifting targets against current features
    for i in range(len(df)):
        if i + lookforward >= len(df):
            labels.append(np.nan) # Drop rows where we can't look forward
            continue

        entry_price = df['close'].iloc[i]
        future_highs = df['high'].iloc[i+1 : i+lookforward+1]
        future_lows = df['low'].iloc[i+1 : i+lookforward+1]

        # Did it hit target before stop?
        hit_target = any(future_highs >= entry_price * (1 + target_return))
        hit_stop = any(future_lows <= entry_price * (1 + stop_loss))

        if hit_target and not hit_stop:
            labels.append(1)
        else:
            labels.append(0)

    df['Target'] = labels
    return df.dropna()

def train_model() -> None:
    """
    Trains a Random Forest Classifier using historical data across the universe.
    """
    log.info("Starting ML Auto-Retraining...")

    all_features = []
    all_targets = []

    # Feature columns expected by the model
    feature_cols = ['EMA_50', 'EMA_200', 'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist', 'ATR_14', 'BB_Upper', 'BB_Lower', 'Log_Return']

    try:
        for name, ticker in UNIVERSE.items():
            # Fetch 5 years of daily data for robust training
            df = _download_yf_data(ticker, "1d", "5y")
            if df.empty:
                continue

            df = add_features(df)
            if df.empty:
                continue

            # Create Labels (Target)
            labeled_df = _create_labels(df)

            # Ensure features are present
            if not all(col in labeled_df.columns for col in feature_cols):
                continue

            # Normalize/Scale features (Optional, RF is robust to unscaled data)
            X = labeled_df[feature_cols]
            y = labeled_df['Target']

            all_features.append(X)
            all_targets.append(y)

        if not all_features:
            log.error("ML Training failed: No valid data found across the universe.")
            return

        X_combined = pd.concat(all_features, ignore_index=True)
        y_combined = pd.concat(all_targets, ignore_index=True)

        # Train/Test Split
        X_train, X_test, y_train, y_test = train_test_split(X_combined, y_combined, test_size=0.2, shuffle=False)

        # Shallow trees to prevent overfitting, n_jobs=-1 for CPU optimization
        rf = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_split=50, n_jobs=-1, random_state=42)
        rf.fit(X_train, y_train)

        # Save Model
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(rf, MODEL_PATH)

        train_acc = rf.score(X_train, y_train)
        test_acc = rf.score(X_test, y_test)
        log.info(f"ML Model Retrained Successfully. Train Acc: {train_acc:.2f}, Test Acc: {test_acc:.2f}")

    except Exception as e:
        log.error(f"Error during ML retraining: {e}")

def validate_signal_with_ml(features_dict: dict, threshold: float = 0.60) -> bool:
    """
    Validates a technical signal using the Random Forest Classifier.
    Returns True if the probability of success is >= threshold.
    """
    try:
        if not os.path.exists(MODEL_PATH):
            log.warning("ML Model not found. Bypassing ML Validation. Please run train_model().")
            return True

        rf = joblib.load(MODEL_PATH)

        # Expected order of features
        feature_cols = ['EMA_50', 'EMA_200', 'RSI_14', 'MACD', 'MACD_Signal', 'MACD_Hist', 'ATR_14', 'BB_Upper', 'BB_Lower', 'Log_Return']

        # Extract features for current timestamp
        input_data = [features_dict.get(col, 0.0) for col in feature_cols]
        X_pred = np.array([input_data])

        # Predict Probability
        prob = rf.predict_proba(X_pred)[0][1] # Probability of class 1 (Success)

        if prob < threshold:
            log.info(f"ML Veto: Signal success probability ({prob:.2f}) < threshold ({threshold}).")
            return False

        log.info(f"ML Approval: Signal success probability ({prob:.2f}) >= threshold ({threshold}).")
        return True

    except Exception as e:
        log.error(f"ML Validation failed: {e}. Bypassing ML.")
        return True
