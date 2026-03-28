import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
from logger import get_logger
from config import MODEL_PATH

log = get_logger()

def create_labels(df: pd.DataFrame, n_forward: int = 10, tp_mult: float = 3.0, sl_mult: float = 1.5) -> pd.Series:
    """
    Creates Target 'y' (1 = Success, 0 = Failure) for ML training.
    Strictly avoids Lookahead Bias by only labelling past data.
    """
    labels = np.zeros(len(df))

    for i in range(len(df) - n_forward):
        entry_price = df['Close'].iloc[i]
        atr = df['ATR_14'].iloc[i]

        tp_long = entry_price + (atr * tp_mult)
        sl_long = entry_price - (atr * sl_mult)

        future_window = df['Close'].iloc[i+1:i+1+n_forward]

        if len(future_window) > 0:
            high_reached = future_window.max() >= tp_long
            low_reached = future_window.min() <= sl_long

            # Simple assumption: if it hit TP before SL, it's a win.
            if high_reached and not low_reached:
                labels[i] = 1

    return pd.Series(labels, index=df.index)

def train_model(historical_df: pd.DataFrame, features: list):
    """Trains a Random Forest Classifier and saves to disk."""
    if len(historical_df) < 500:
        log.warning("Not enough data to train ML model.")
        return False

    df = historical_df.copy()
    y = create_labels(df)
    X = df[features]

    # Drop NaNs
    valid_idx = X.dropna().index.intersection(y[y.notna()].index)
    X = X.loc[valid_idx]
    y = y.loc[valid_idx]

    # Drop last n_forward rows to avoid training on incomplete labels
    X = X.iloc[:-10]
    y = y.iloc[:-10]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False) # Time-series split

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)

    score = model.score(X_test, y_test)
    log.info(f"ML Model Trained. OOS Accuracy: {score:.2%}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    return True

def predict_proba_veto(features_dict: dict, threshold: float = 0.60) -> bool:
    """
    Predicts probability of success. Returns True to VETO if probability < threshold.
    """
    try:
        if not os.path.exists(MODEL_PATH):
            return False # No model yet, don't veto

        model = joblib.load(MODEL_PATH)

        # Ensure features_dict matches the training features exactly
        X_new = pd.DataFrame([features_dict])

        proba = model.predict_proba(X_new)[0][1] # Probability of class 1 (Success)

        if proba < threshold:
            log.warning(f"ML VETO: Probability {proba:.2%} < {threshold:.2%}. Rejecting signal.")
            return True
        return False
    except Exception as e:
        log.error(f"Error in ML Veto: {e}")
        return False
