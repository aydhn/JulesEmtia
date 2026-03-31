import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
from features import add_features
from logger import setup_logger

logger = setup_logger("MLValidator")

MODEL_PATH = "rf_model.pkl"

def train_and_save_model(historical_data: pd.DataFrame, ticker: str):
    """Trains a Random Forest Classifier to validate signals. Calculates Win/Loss labels on historical data."""
    if historical_data.empty or len(historical_data) < 500:
        logger.warning(f"Yeterli veri yok, ML modeli eğitilemedi: {ticker}")
        return

    # Add technical features
    df = add_features(historical_data)

    # Create Labels (Target Variable)
    # 1: Trade was profitable (hit TP before SL within N bars)
    # 0: Trade was unprofitable (hit SL or timed out)
    # Simplified approach: Look ahead N bars, if max high > entry + TP distance, label 1.

    # We use a simple future return proxy here for demonstration
    # Shift(-N) looks into the future. This is ONLY for training, NOT for live execution!
    N_BARS = 10
    df['Future_Return'] = df['Close'].shift(-N_BARS) / df['Close'] - 1

    # If it gained more than 0.5% in N bars, we consider it a 'Win' (1), else 'Loss' (0)
    df['Target'] = np.where(df['Future_Return'] > 0.005, 1, 0)

    # Drop rows with NaN targets (the last N rows)
    df.dropna(subset=['Target'], inplace=True)

    # Select Features (X)
    features = ['EMA_50', 'EMA_200', 'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return']

    # Ensure all features exist
    for f in features:
        if f not in df.columns:
            logger.error(f"Eksik özellik: {f}. ML Eğitimi İptal.")
            return

    X = df[features]
    y = df['Target']

    # Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    # Train Random Forest (Shallow depth to prevent overfitting)
    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    # Evaluate
    score = clf.score(X_test, y_test)
    logger.info(f"ML Modeli Eğitildi [{ticker}] - Out-of-Sample Doğruluk: %{score*100:.2f}")

    # Save Model
    joblib.dump(clf, MODEL_PATH)
    logger.info(f"Model diske kaydedildi: {MODEL_PATH}")

def validate_signal_with_ml(current_features: pd.Series, threshold: float = 0.60) -> bool:
    """Uses the trained model to predict the probability of success for a new signal."""
    if not os.path.exists(MODEL_PATH):
        logger.warning("ML Modeli bulunamadı. Veto devre dışı bırakılıyor (Pass-through).")
        return True # Pass if no model

    try:
        clf = joblib.load(MODEL_PATH)
        features = ['EMA_50', 'EMA_200', 'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return']

        # Extract features into 2D array for prediction
        X_live = np.array([current_features[features].values])

        # Predict probability of class 1 (Win)
        prob_win = clf.predict_proba(X_live)[0][1]

        if prob_win >= threshold:
            logger.info(f"ML Onayı Başarılı: Kazanma İhtimali %{prob_win*100:.2f}")
            return True
        else:
            logger.warning(f"ML Vetosu: Kazanma İhtimali Düşük (%{prob_win*100:.2f} < %{threshold*100:.0f}). Sinyal Reddedildi.")
            return False

    except Exception as e:
        logger.error(f"ML Doğrulama hatası: {str(e)}")
        return True # Fail open
