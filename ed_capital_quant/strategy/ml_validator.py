import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib
import os

from core.logger import logger

MODEL_PATH = "models/rf_validator.pkl"

class MLValidator:
    """Teknik sinyallerin geçmiş veriler üzerinde (Random Forest) doğrulamasını sağlayan AI Veto Katmanı."""

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_trained = True
                logger.info("Yapay Zeka Doğrulama Modeli (ML Validator) yüklendi.")
            except Exception as e:
                logger.error(f"Model Yükleme Hatası: {e}")

    def create_labels(self, df: pd.DataFrame, target_col: str = 'Close', n_bars: int = 5, tp_pct: float = 0.01) -> pd.DataFrame:
        """Geçmiş veriye bakarak 'Başarılı İşlem (1)' ve 'Başarısız İşlem (0)' etiketleri üretir."""
        df['Target_Return'] = df[target_col].shift(-n_bars) / df[target_col] - 1
        # Hedeflenen Kâr (TP) veya üzerinde getiri sağladıysa "1" (Başarılı)
        df['Signal_Success'] = np.where(df['Target_Return'] >= tp_pct, 1, 0)

        # Gelecekteki veriyi (Target_Return) ML modeline SOKMAYIZ! (Lookahead Bias önlemi)
        return df.drop(columns=['Target_Return'])

    def train_model(self, df_features: pd.DataFrame, feature_cols: list):
        """Random Forest modelini yerel CPU'da eğitir."""
        logger.info("ML Validator Modeli eğitiliyor...")
        df = df_features.copy()
        df = self.create_labels(df)
        df = df.dropna()

        X = df[feature_cols]
        y = df['Signal_Success']

        if len(X) < 100:
            logger.warning("ML Eğitimi İptal: Yetersiz Veri.")
            return

        # Basit bir 80/20 Test/Train ayrımı
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)
        acc = accuracy_score(y_test, preds)
        logger.info(f"Model Eğitimi Tamamlandı. Out-of-Sample Doğruluk (Accuracy): {acc:.2f}")

        # Modeli Kaydet
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        self.is_trained = True

    def validate_signal(self, current_features: np.ndarray, threshold: float = 0.60) -> bool:
        """Sinyal geldiğinde modelden onay ister. Eğer olasılık %60 altındaysa VETO eder."""
        if not self.is_trained:
            return True # Model eğitilmemişse engelleme

        # probability for class 1 (Başarı İhtimali)
        success_prob = self.model.predict_proba([current_features])[0][1]

        if success_prob < threshold:
            logger.warning(f"ML VETOSU: Sinyalin başarı ihtimali çok düşük ({success_prob:.2f}). Sinyal Reddedildi.")
            return False # Reddet (Veto)

        logger.info(f"ML ONAYI: Sinyalin başarı ihtimali Yüksek ({success_prob:.2f}). Onaylandı.")
        return True # Onaylandı