import os
import time
import asyncio
import feedparser
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from typing import Tuple

from .infrastructure import logger
from .config import TICKERS, SENTIMENT_THRESHOLD_LONG, SENTIMENT_THRESHOLD_SHORT

class SentimentEngine:
    """Phase 20: NLP VADER Sentiment Analysis via Free RSS Feeds."""
    def __init__(self):
        try:
            self.sia = SentimentIntensityAnalyzer()
        except LookupError:
            import nltk
            nltk.download('vader_lexicon', quiet=True)
            self.sia = SentimentIntensityAnalyzer()

        self.rss_urls = [
            "https://finance.yahoo.com/news/rssindex",
            "https://www.investing.com/rss/news_285.rss" # Commodities
        ]
        self.cache = {}
        self.cache_ttl = 3600 # 1 hour

    async def fetch_sentiment(self, ticker_category: str) -> float:
        """Fetch RSS feeds and analyze sentiment asynchronously."""
        current_time = time.time()
        if ticker_category in self.cache:
            score, timestamp = self.cache[ticker_category]
            if current_time - timestamp < self.cache_ttl:
                return score

        logger.info(f"Fetching RSS News Sentiment for {ticker_category}...")

        keywords = {
            "METALS": ["gold", "silver", "copper", "metal", "mining", "palladium", "platinum"],
            "ENERGY": ["oil", "gas", "crude", "brent", "opec", "energy"],
            "AGRI": ["wheat", "corn", "soybean", "coffee", "sugar", "agriculture", "crop", "cattle"],
            "FOREX": ["lira", "try", "turkey", "inflation", "cbrt", "fed", "rates", "dollar", "euro"]
        }

        target_keywords = keywords.get(ticker_category, [])

        loop = asyncio.get_event_loop()

        def parse_feeds():
            scores = []
            for url in self.rss_urls:
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries:
                        title = entry.title.lower()
                        # If any keyword matches the title
                        if any(kw in title for kw in target_keywords):
                            sentiment = self.sia.polarity_scores(entry.title)
                            scores.append(sentiment['compound'])
                except Exception as e:
                    logger.warning(f"RSS Feed error on {url}: {e}")
            return scores

        compound_scores = await loop.run_in_executor(None, parse_feeds)

        if not compound_scores:
            final_score = 0.0 # Neutral if no news
        else:
            final_score = sum(compound_scores) / len(compound_scores)

        self.cache[ticker_category] = (final_score, current_time)
        logger.info(f"Sentiment Score for {ticker_category}: {final_score:.3f}")
        return final_score

    def get_sentiment_veto(self, direction: str, ticker_category: str) -> bool:
        """Phase 20: Haber akışı ters yönlüyse vetoyu bas"""
        if ticker_category not in self.cache:
            return False

        score = self.cache[ticker_category][0]

        if direction == "LONG" and score < SENTIMENT_THRESHOLD_LONG:
            logger.warning(f"Sentiment Veto! Long rejected for {ticker_category}. Score: {score:.2f}")
            return True
        elif direction == "SHORT" and score > SENTIMENT_THRESHOLD_SHORT:
            logger.warning(f"Sentiment Veto! Short rejected for {ticker_category}. Score: {score:.2f}")
            return True

        return False

# ----------------- MACHINE LEARNING (Phase 18) -----------------
class MLValidator:
    def __init__(self, model_path="models/rf_validator.pkl"):
        self.model_path = model_path
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            self.is_trained = True
            logger.info("ML Model loaded from disk.")

    def _create_labels(self, df: pd.DataFrame, lookahead=5, atr_tp=2.0, atr_sl=1.0) -> pd.DataFrame:
        """Create labels for ML without lookahead bias."""
        df['Target'] = 0
        for i in range(len(df) - lookahead):
            current_close = df['Close'].iloc[i]
            current_atr = df['ATRr_14'].iloc[i] if 'ATRr_14' in df.columns else current_close * 0.01
            if pd.isna(current_atr): continue

            tp_price = current_close + (atr_tp * current_atr)
            sl_price = current_close - (atr_sl * current_atr)
            window = df.iloc[i+1 : i+1+lookahead]
            hit_tp = False
            for _, row in window.iterrows():
                if row['Low'] <= sl_price: break
                if row['High'] >= tp_price:
                    hit_tp = True
                    break
            df.iat[i, df.columns.get_loc('Target')] = 1 if hit_tp else 0

        df = df.iloc[:-lookahead].copy()
        df.dropna(inplace=True)
        return df

    def train(self, historical_df: pd.DataFrame):
        logger.info("Training Random Forest Classifier...")

        # Determine features based on availability in historical_df
        available_features = [
            'RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return', 'ADX_14',
            'MFI_14', 'OBV', 'CMF_20'
        ]

        features = [f for f in available_features if f in historical_df.columns]

        if not features:
            logger.warning("No features available for ML Training.")
            return

        df_train = self._create_labels(historical_df.copy())

        # Ensure all features exist in df_train after label creation
        valid_features = [f for f in features if f in df_train.columns]

        if not valid_features:
            logger.warning("No valid features remaining after label creation.")
            return

        X = df_train[valid_features]
        y = df_train['Target']

        if len(X) < 100:
            logger.warning("Not enough data to train ML Model.")
            return

        self.model.fit(X, y)
        self.feature_names_in_ = valid_features # Store used features
        joblib.dump({'model': self.model, 'features': self.feature_names_in_}, self.model_path)
        self.is_trained = True
        logger.info("ML Model trained and saved.")

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                saved_data = joblib.load(self.model_path)
                if isinstance(saved_data, dict) and 'model' in saved_data and 'features' in saved_data:
                    self.model = saved_data['model']
                    self.feature_names_in_ = saved_data['features']
                else:
                    # Legacy fallback
                    self.model = saved_data
                    self.feature_names_in_ = ['RSI_14', 'MACDh_12_26_9', 'ATRr_14', 'Log_Return', 'ADX_14']
                self.is_trained = True
                logger.info("ML Model loaded from disk.")
            except Exception as e:
                logger.error(f"Error loading ML model: {e}")

    def validate_signal(self, current_features: pd.DataFrame, direction: str) -> bool:
        if not self.is_trained: return True

        if not hasattr(self, 'feature_names_in_'):
            logger.warning("ML Model doesn't have feature names stored. Allowing signal.")
            return True

        if any(f not in current_features.columns for f in self.feature_names_in_):
            logger.warning("Current features missing required columns for ML. Allowing signal.")
            return True

        X = current_features[self.feature_names_in_].iloc[-1:]
        probs = self.model.predict_proba(X)[0]
        threshold = 0.60

        if direction == "LONG" and probs[1] > threshold:
            logger.info(f"ML Veto Passed: Long Probability {probs[1]:.2%}")
            return True
        elif direction == "SHORT" and probs[0] > threshold:
            logger.info(f"ML Veto Passed: Short Probability {probs[0]:.2%}")
            return True

        logger.warning(f"ML Veto Rejected: Probability {max(probs[0], probs[1]):.2%} for {direction}")
        return False
