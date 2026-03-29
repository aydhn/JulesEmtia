import os
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from core.logger import get_logger

logger = get_logger()

class MLValidator:
    def __init__(self):
        self.model_path = "data/ml_validator.pkl"
        self.model = self._load_or_train_ml()

    def _load_or_train_ml(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.model_path):
            try:
                return joblib.load(self.model_path)
            except Exception as e:
                logger.error(f"ML Model Load Error: {e}")

        logger.info("Training initial ML Validator Model...")
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

        # Fake data for bootstrapping, real data will be retrained periodically
        X = np.random.rand(500, 3) # RSI, Z_Score, ATR
        y = np.random.randint(0, 2, 500)
        clf.fit(X, y)

        joblib.dump(clf, self.model_path)
        return clf

    def ml_veto(self, features: list, threshold: float = 0.60) -> bool:
        try:
            prob = self.model.predict_proba(np.array(features).reshape(1, -1))[0][1]
            return prob < threshold
        except Exception as e:
            logger.error(f"ML Predict Error: {e}")
            return False
