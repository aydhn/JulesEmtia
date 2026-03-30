import os
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import feedparser
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib
from system.logger import log

nltk.download('vader_lexicon', quiet=True)

class NLPFilter:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.rss = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"

    def get_sentiment_veto(self, direction: str) -> bool:
        """Phase 20: Haber akışı ters yönlüyse vetoyu bas"""
        try:
            feed = feedparser.parse(self.rss)
            entries = feed.entries[:10]
            if not entries:
                return False

            score = sum(self.sia.polarity_scores(e.title)['compound'] for e in entries) / len(entries)

            if (direction == "LONG" and score < -0.3) or (direction == "SHORT" and score > 0.3):
                log.warning(f"Temel Analiz Vetosu! Sentiment Skoru: {score:.2f}")
                return True
        except Exception as e:
            log.warning(f"Sentiment API Error: {e}")
        return False

class MLValidator:
    def __init__(self):
        self.model_path = "rf_model.pkl"
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def train_if_needed(self, df: pd.DataFrame, force: bool = False):
        """Phase 18: Geleceği bilmeden, geçmiş veriyle RandomForest eğit"""
        if (os.path.exists(self.model_path) and not force) or df.empty:
            return

        df = df.copy()
        df['Target'] = (df['Close'].shift(-10) > df['Close']).astype(int)

        # Calculate features if missing
        if 'EMA_50' not in df.columns:
            import pandas_ta as ta
            df.ta.ema(length=50, append=True)
            df.ta.rsi(length=14, append=True)
            df.rename(columns={'EMA_50': 'EMA_50', 'RSI_14': 'RSI_14'}, inplace=True)

        df.dropna(inplace=True)

        required_cols = ['EMA_50', 'RSI_14']
        if not all(col in df.columns for col in required_cols):
            return

        X = df[required_cols] # Temsili özellikler
        if len(X) > 100:
            try:
                self.model.fit(X, df['Target'])
                joblib.dump(self.model, self.model_path)
                log.info("ML Modeli eğitildi.")
            except Exception as e:
                log.error(f"Failed to train ML model: {e}")

    def validate(self, features: dict, direction: str) -> bool:
        if not os.path.exists(self.model_path):
            return True

        try:
            model = joblib.load(self.model_path)
            prob = model.predict_proba(pd.DataFrame([features]))[0]
            if (direction == "LONG" and prob[1] < 0.6) or (direction == "SHORT" and prob[0] < 0.6):
                log.warning(f"Makine Öğrenmesi İhtimali Düşük Buldu. Sinyal Reddedildi. (Prob: {prob})")
                return False
        except Exception as e:
            log.warning(f"ML Validation error: {e}")

        return True
