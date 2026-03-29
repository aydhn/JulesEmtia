import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import numpy as np
import time
from core.logger import get_logger
logger = get_logger()

class SentimentFilter:
    def __init__(self):
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
        self.sia = SentimentIntensityAnalyzer()
        self.news_cache = {}
        self.cache_time = 0

    def get_news_sentiment(self, keyword="economy") -> float:
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
