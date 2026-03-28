import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
import os

MODEL_PATH = "models/rf_model.pkl"

def train_model(X, y):
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)
    joblib.dump(model, MODEL_PATH)

def validate_signal(features: pd.DataFrame) -> bool:
    if not os.path.exists(MODEL_PATH):
        return True # Default to accept if no model
    model = joblib.load(MODEL_PATH)
    prob = model.predict_proba(features.iloc[-1:])
    return prob[0][1] > 0.60
