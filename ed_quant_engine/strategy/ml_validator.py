import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from core.logger import get_logger

logger = get_logger()

class MLValidator:
    def __init__(self):
        self.model_path = "ml_model.pkl"
        self.model = self._load_model()
        self.threshold = 0.60 # %60 confidence required

    def _load_model(self):
        if os.path.exists(self.model_path):
            return joblib.load(self.model_path)
        return RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def train_model(self, df: pd.DataFrame):
        """Trains the Random Forest on historical signals."""
        try:
            # Future (Next 10 bars return > 1%)
            df['Future_Return'] = df['Close'].shift(-10) / df['Close'] - 1
            df['Target'] = (df['Future_Return'] > 0.01).astype(int)

            features = ['RSI', 'Z_Score', 'ATR', 'Log_Return']
            X = df[features].dropna()
            y = df['Target'].loc[X.index]

            self.model.fit(X, y)
            joblib.dump(self.model, self.model_path)
            logger.info("Makine Öğrenmesi Modeli başarıyla yeniden eğitildi ve kaydedildi.")
        except Exception as e:
            logger.error(f"ML Eğitim Hatası: {e}")

    def ml_veto(self, current_features: list) -> bool:
        """Returns True if the ML model vetoes the signal (Probability < Threshold)."""
        if not hasattr(self.model, "predict_proba"):
            return False # Bypass if model not trained yet

        try:
            X_live = pd.DataFrame([current_features], columns=['RSI', 'Z_Score', 'ATR'])
            prob_success = self.model.predict_proba(X_live)[0][1]

            if prob_success < self.threshold:
                return True # Veto!
            return False # Approved
        except Exception:
            return False
