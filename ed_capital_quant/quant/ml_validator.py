from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import numpy as np
from core.logger import logger

class MLValidator:
    def __init__(self, model_path="quant_model.pkl"):
        self.model_path = model_path
        self.model = RandomForestClassifier(max_depth=5, n_estimators=100, random_state=42)
        self.is_trained = os.path.exists(model_path)
        if self.is_trained:
            try:
                self.model = joblib.load(model_path)
                logger.info("ML Modeli başarıyla yüklendi.")
            except Exception as e:
                logger.warning(f"ML Modeli yüklenemedi: {e}")
                self.is_trained = False

    def train(self, features: np.ndarray, labels: np.ndarray):
        if len(features) < 10:
            logger.warning("Eğitim için yeterli veri yok.")
            return

        self.model.fit(features, labels)
        joblib.dump(self.model, self.model_path)
        self.is_trained = True
        logger.info("ML Modeli eğitildi ve kaydedildi.")

    def validate_signal(self, current_features: np.ndarray) -> bool:
        if not self.is_trained:
            return True

        try:
            # Reshape feature vector to 2D array expected by sklearn
            # current_features should be shape (n_features,)
            feat_array = current_features.reshape(1, -1)

            prob = self.model.predict_proba(feat_array)[0]
            # Assumes class 1 is "Success"
            success_prob = prob[1] if len(prob) > 1 else 0.0

            if success_prob < 0.60:
                logger.info(f"ML Vetosu: Başarı ihtimali düşük (%{success_prob*100:.1f})")
                return False
        except Exception as e:
            logger.error(f"ML Validation hatası: {e}")

        return True
