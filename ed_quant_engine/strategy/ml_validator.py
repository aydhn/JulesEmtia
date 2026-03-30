import os
import pickle
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from core.logger import get_logger

log = get_logger()
MODEL_PATH = 'models/rf_validator.pkl'
os.makedirs('models', exist_ok=True)

def train_model(df: pd.DataFrame, target_returns_col: str = 'Log_Return', lookforward: int = 5):
    # Shift returns backward to create targets
    # 1 if price went up after signal, 0 otherwise
    df['Target'] = (df[target_returns_col].rolling(lookforward).sum().shift(-lookforward) > 0).astype(int)

    # Features
    features = ['RSI_14', 'MACD', 'ATR_14', 'Log_Return']
    df_clean = df.dropna(subset=features + ['Target'])

    X = df_clean[features]
    y = df_clean['Target']

    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    clf.fit(X, y)

    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(clf, f)

    log.info(f"ML Validator trained and saved to {MODEL_PATH}. Accuracy: {clf.score(X,y):.2f}")
    return clf

def validate_signal(current_features: pd.DataFrame) -> float:
    try:
        if not os.path.exists(MODEL_PATH):
            return 0.5 # Default probability if no model

        with open(MODEL_PATH, 'rb') as f:
            clf = pickle.load(f)

        features = ['RSI_14', 'MACD', 'ATR_14', 'Log_Return']
        X_pred = current_features[features].iloc[-1:]

        prob = clf.predict_proba(X_pred)[0][1] # Probability of Class 1 (Success)
        return prob
    except Exception as e:
        log.error(f"ML Validation Error: {e}")
        return 0.5
