import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
from utils.logger import log

MODEL_PATH = "models/rf_model.pkl"

def create_labels(df: pd.DataFrame, lookahead: int = 10) -> pd.DataFrame:
    # Phase 18: Shift future returns back to current row to label success/failure
    # Avoid lookahead bias in features: Features are computed up to T, labels are T+1 to T+10

    # Example logic: did it gain 1% before losing 0.5% in the next N periods?
    # Simplified here to: was the return N periods later positive?
    future_returns = df['Close'].shift(-lookahead) / df['Close'] - 1

    # 1 if positive return, 0 if negative or flat
    df['Target'] = np.where(future_returns > 0.005, 1, 0)

    return df

def train_model(features: pd.DataFrame):
    df = features.copy()

    # Add labels
    df = create_labels(df)

    # Drop rows with NaN targets (the last N rows due to shift)
    df.dropna(subset=['Target'], inplace=True)

    if len(df) < 50:
        log.warning("Not enough data to train ML model")
        return

    # Select feature columns (drop Target and raw prices if needed)
    feature_cols = [c for c in df.columns if c not in ['Target', 'Close', 'Close_HTF']]

    X = df[feature_cols]
    y = df['Target']

    # Phase 18: Train a lightweight robust model
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)

    log.info("Eğitim Başladı: Random Forest Classifier")
    model.fit(X, y)

    # Save the model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump((model, feature_cols), MODEL_PATH)
    log.info(f"Model Eğitildi ve Kaydedildi: {MODEL_PATH}")

def validate_signal(features: pd.DataFrame) -> bool:
    if not os.path.exists(MODEL_PATH):
        # If no model exists yet, we allow the trade (fallback)
        return True

    try:
        model, feature_cols = joblib.load(MODEL_PATH)

        # Ensure the incoming features match what the model expects
        X_pred = features[feature_cols].iloc[-1:] # Take only the last row

        # Predict probability of class 1 (Success)
        prob = model.predict_proba(X_pred)

        if len(prob[0]) > 1:
            success_prob = prob[0][1]
        else:
            # Only one class was learned (extreme case)
            success_prob = float(model.classes_[0] == 1)

        if success_prob < 0.60:
            log.info(f"ML Vetosu: Olasılık {success_prob:.2f} < 0.60. Sinyal reddedildi.")
            return False

        return True

    except Exception as e:
        log.error(f"ML Tahmin Hatası: {e}")
        # In case of error, fail open to not block the system entirely
        return True
