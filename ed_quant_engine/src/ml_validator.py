import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.logger import get_logger

logger = get_logger()
MODEL_PATH = "models/rf_model.pkl"

def create_labels(df: pd.DataFrame, horizon: int = 5, tp_mult: float = 1.0, sl_mult: float = 0.5):
    """
    Creates target labels for ML training. 1 if hit TP before SL within 'horizon', 0 otherwise.
    Strictly avoids lookahead bias by shifting target calculations backwards, then dropping NaNs.
    """
    labels = np.zeros(len(df))
    for i in range(len(df) - horizon):
        entry_price = df['Close'].iloc[i]
        atr = df['ATR_14'].iloc[i] if 'ATR_14' in df.columns else entry_price * 0.01

        # Simplified simulation for Long labeling
        tp = entry_price + (atr * tp_mult)
        sl = entry_price - (atr * sl_mult)

        success = 0
        for j in range(1, horizon + 1):
            if df['High'].iloc[i+j] >= tp:
                success = 1
                break
            if df['Low'].iloc[i+j] <= sl:
                success = 0
                break
        labels[i] = success

    df['Target'] = labels
    # Drop last 'horizon' rows as we can't know their future outcome
    return df.iloc[:-horizon].copy()

def train_model(historical_df: pd.DataFrame):
    """
    Trains a Random Forest model on historical data.
    """
    os.makedirs("models", exist_ok=True)
    if len(historical_df) < 500:
        logger.warning("Not enough data to train ML model.")
        return

    features = ['RSI_14', 'ATR_14', 'Log_Ret']
    # Add MACD histograms if present (pandas_ta generates dynamic names, finding them safely)
    macd_cols = [c for c in historical_df.columns if c.startswith('MACDh')]
    if macd_cols:
        features.append(macd_cols[0])

    df = create_labels(historical_df)
    df.dropna(subset=features + ['Target'], inplace=True)

    X = df[features]
    y = df['Target']

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)

    joblib.dump(model, MODEL_PATH)
    logger.info(f"ML Model trained and saved to {MODEL_PATH}")

def validate_signal(current_features: pd.Series, threshold: float = 0.55) -> bool:
    """
    Validates a signal using the trained ML model. Returns True if probability > threshold.
    """
    if not os.path.exists(MODEL_PATH):
        logger.warning("ML Model not found. Bypassing ML validation.")
        return True # Bypass if no model

    try:
        model = joblib.load(MODEL_PATH)
        features = ['RSI_14', 'ATR_14', 'Log_Ret']
        macd_cols = [c for c in current_features.index if c.startswith('MACDh')]

        input_data = []
        for f in features:
            input_data.append(current_features.get(f, 0.0))
        if macd_cols:
             input_data.append(current_features.get(macd_cols[0], 0.0))

        # Reshape for single prediction
        X_test = np.array(input_data).reshape(1, -1)
        prob = model.predict_proba(X_test)[0][1] # Prob of class 1

        if prob >= threshold:
            return True
        else:
            logger.info(f"ML Veto: Signal rejected. Probability {prob:.2f} < {threshold}")
            return False
    except Exception as e:
        logger.error(f"Error in ML validation: {e}")
        return True # Fallback to True if error
