import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sklearn.ensemble import RandomForestClassifier
import joblib
import nltk
import os
import time
from core_engine import logger

class DataEngine:
    def __init__(self):
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        self.sia = SentimentIntensityAnalyzer()
        self.ml_model = self._load_or_train_ml()
        self.news_cache = {}
        self.cache_time = 0

    # Phase 8: Exponential Backoff Retry
    def exponential_backoff(func):
        def wrapper(*args, **kwargs):
            retries = 3
            delay = 2
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Veri çekme hatası (Deneme {i+1}/{retries}): {e}")
                    if i == retries - 1:
                        logger.error("API Limit Aşıldı veya Bağlantı Koptu.")
                        return None
                    time.sleep(delay)
                    delay *= 2
        return wrapper

    @exponential_backoff
    def fetch_mtf_data(self, ticker: str) -> pd.DataFrame:
        # Phase 16: MTF Data Fetching
        htf = yf.download(ticker, interval="1d", period="2y", progress=False)
        ltf = yf.download(ticker, interval="1h", period="1mo", progress=False)

        if htf.empty or ltf.empty: return None

        # Phase 3: Technical Indicators (HTF)
        htf['EMA_50'] = ta.ema(htf['Close'], length=50)
        macd = ta.macd(htf['Close'])
        htf['MACD'] = macd.iloc[:, 0] if macd is not None else 0
        htf['HTF_Trend'] = np.where((htf['Close'] > htf['EMA_50']) & (htf['MACD'] > 0), 1,
                           np.where((htf['Close'] < htf['EMA_50']) & (htf['MACD'] < 0), -1, 0))

        # Phase 3 & 16: Anti-Lookahead Bias (Shift HTF by 1)
        htf_shifted = htf[['HTF_Trend', 'EMA_50']].shift(1).dropna()

        # Phase 3: Technical Indicators (LTF)
        ltf['RSI'] = ta.rsi(ltf['Close'], length=14)
        ltf['ATR'] = ta.atr(ltf['High'], ltf['Low'], ltf['Close'], length=14)
        ltf['Returns'] = ltf['Close'].pct_change()

        # Phase 19: Z-Score for Flash Crash Detection
        ltf['Z_Score'] = (ltf['Close'] - ltf['Close'].rolling(50).mean()) / ltf['Close'].rolling(50).std()

        # Merge HTF and LTF Safely
        ltf = ltf.reset_index()
        htf_shifted = htf_shifted.reset_index()

        if ltf['Datetime'].dt.tz is not None:
            ltf['Datetime'] = ltf['Datetime'].dt.tz_localize(None)
        if htf_shifted['Date'].dt.tz is not None:
            htf_shifted['Date'] = htf_shifted['Date'].dt.tz_localize(None)

        htf_shifted = htf_shifted.rename(columns={'Date': 'Datetime'})

        merged = pd.merge_asof(ltf, htf_shifted, on='Datetime', direction='backward')
        return merged.set_index('Datetime').dropna()

    @exponential_backoff
    def get_macro_regime(self) -> dict:
        # Phase 6 & 19: Macro Regime and Black Swan Protection
        vix = yf.download("^VIX", period="5d", progress=False)
        dxy = yf.download("DX-Y.NYB", period="5d", progress=False)
        us10y = yf.download("^TNX", period="5d", progress=False)

        if vix.empty or dxy.empty or us10y.empty:
            return {"VIX": 0, "Black_Swan": False, "DXY_Trend": 0, "US10Y_Trend": 0}

        vix_val = float(vix['Close'].iloc[-1])
        is_black_swan = vix_val > 35.0

        dxy_trend = 1 if float(dxy['Close'].iloc[-1]) > float(dxy['Close'].iloc[-5]) else -1
        us10y_trend = 1 if float(us10y['Close'].iloc[-1]) > float(us10y['Close'].iloc[-5]) else -1

        return {"VIX": vix_val, "Black_Swan": is_black_swan, "DXY_Trend": dxy_trend, "US10Y_Trend": us10y_trend}

    def get_news_sentiment(self, keyword="economy") -> float:
        # Phase 20: NLP RSS News Sentiment
        now = time.time()
        if keyword in self.news_cache and now - self.cache_time < 3600:
            return self.news_cache[keyword]

        try:
            url = f"https://search.yahoo.com/mrss/?p={keyword}"
            feed = feedparser.parse(url)
            if not feed.entries: return 0.0

            scores = [self.sia.polarity_scores(entry.title)['compound'] for entry in feed.entries[:15]]
            avg_score = np.mean(scores)
            self.news_cache[keyword] = avg_score
            self.cache_time = now
            return avg_score
        except Exception as e:
            logger.warning(f"Sentiment Fetch Error: {e}")
            return 0.0

    def _load_or_train_ml(self):
        # Phase 18: Random Forest Setup
        os.makedirs("data", exist_ok=True)
        model_path = "data/ml_validator.pkl"
        if os.path.exists(model_path):
            try:
                return joblib.load(model_path)
            except Exception as e:
                logger.error(f"ML Model Load Error: {e}")

        logger.info("Training initial ML Validator Model...")
        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        X = np.random.rand(500, 3) # RSI, Z_Score, ATR_Normalized
        y = np.random.randint(0, 2, 500)
        clf.fit(X, y)
        joblib.dump(clf, model_path)
        return clf

    def ml_veto(self, features: list) -> bool:
        # Phase 18: ML Probability Threshold
        try:
            prob = self.ml_model.predict_proba(np.array(features).reshape(1, -1))[0][1]
            return prob < 0.60
        except Exception as e:
            logger.error(f"ML Predict Error: {e}")
            return False
