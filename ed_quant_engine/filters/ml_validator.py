import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib
import os
import asyncio
from features import add_features
from data_loader import fetch_historical_data
from utils.logger import setup_logger

logger = setup_logger("MLValidator")

MODEL_PATH = "rf_model.pkl"

# Exact features matching pandas_ta generation in features.py
ML_FEATURES = ['EMA_50', 'EMA_200', 'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return']

async def ensure_ml_model():
    """Ensures that the ML model is trained and available."""
    if not os.path.exists(MODEL_PATH):
        logger.info("ML Modeli bulunamadı. Sıfırdan eğitiliyor...")
        # Train on a major asset for base logic, e.g., Gold
        historical_data = await fetch_historical_data("GC=F", period="5y", interval="1d")
        train_and_save_model(historical_data, "GC=F")

def train_and_save_model(historical_data: pd.DataFrame, ticker: str):
    """
    Phase 18: Trains a Random Forest Classifier to validate signals.
    """
    if historical_data.empty or len(historical_data) < 500:
        logger.warning(f"Yeterli veri yok, ML modeli eğitilemedi: {ticker}")
        return

    # Add technical features
    df = add_features(historical_data)

    # Future return proxy for training target (Phase 18 logic)
    N_BARS = 10
    df['Future_Return'] = df['Close'].shift(-N_BARS) / df['Close'] - 1
    df['Target'] = np.where(df['Future_Return'] > 0.005, 1, 0)
    df.dropna(subset=['Target'] + ML_FEATURES, inplace=True)

    # Ensure all features exist
    for f in ML_FEATURES:
        if f not in df.columns:
            logger.error(f"Eksik özellik: {f}. ML Eğitimi İptal.")
            return

    X = df[ML_FEATURES]
    y = df['Target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
    clf.fit(X_train, y_train)

    score = clf.score(X_test, y_test)
    logger.info(f"ML Modeli Eğitildi [{ticker}] - Out-of-Sample Doğruluk: %{score*100:.2f}")

    joblib.dump(clf, MODEL_PATH)
    logger.info(f"Model diske kaydedildi: {MODEL_PATH}")

def validate_signal_with_ml(current_features: pd.Series, threshold: float = 0.60) -> bool:
    """Uses the trained model to predict the probability of success for a new signal."""
    if not os.path.exists(MODEL_PATH):
        logger.warning("ML Modeli bulunamadı. Veto devre dışı bırakılıyor (Pass-through).")
        return True

    try:
        clf = joblib.load(MODEL_PATH)

        # Extract exact features
        X_live = np.array([current_features[ML_FEATURES].values])

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
