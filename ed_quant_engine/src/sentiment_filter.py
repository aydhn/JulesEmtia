import feedparser
from nltk.sentiment import SentimentIntensityAnalyzer
import nltk
from src.logger import logger
from src.config import ALL_TICKERS
from datetime import datetime, timedelta

# Download VADER lexicon if not already present
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

class SentimentFilter:
    def __init__(self, cache_ttl_hours: int = 12, threshold: float = -0.3):
        self.sia = SentimentIntensityAnalyzer()
        self.rss_feeds = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,SI=F,CL=F,EURUSD=X", # Example Yahoo feeds
            # Add more relevant feeds
        ]
        self.cache = {}
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.threshold = threshold

    def _fetch_news(self) -> list:
        headlines = []
        for url in self.rss_feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    headlines.append(entry.title)
            except Exception as e:
                logger.error(f"Error fetching RSS from {url}: {e}")
        return headlines

    def update_sentiment_cache(self):
        """
        Fetches news, calculates average sentiment, and stores in cache.
        """
        headlines = self._fetch_news()
        if not headlines:
            logger.warning("No news headlines fetched.")
            return

        total_compound = 0
        for text in headlines:
            score = self.sia.polarity_scores(text)['compound']
            total_compound += score

        avg_sentiment = total_compound / len(headlines) if headlines else 0

        # Simplified: one global macro sentiment for now.
        # Can be enhanced to search for ticker-specific keywords in headlines.
        self.cache['macro'] = {
            'score': avg_sentiment,
            'timestamp': datetime.now()
        }
        logger.info(f"Updated Sentiment Cache. Macro Score: {avg_sentiment:.2f}")

    def veto_signal(self, ticker: str, direction: str) -> bool:
        """
        Returns True if the signal is vetoed based on sentiment.
        """
        # 1. Check if cache is valid
        if 'macro' not in self.cache or datetime.now() - self.cache['macro']['timestamp'] > self.cache_ttl:
             logger.warning("Sentiment cache missing or stale. Fetching now.")
             self.update_sentiment_cache()

        score = self.cache.get('macro', {}).get('score', 0)

        # 2. Apply Veto Logic
        # Ex: If Long signal but sentiment is very negative -> Veto
        if direction == "Long" and score <= self.threshold:
             logger.info(f"Sentiment Veto: {direction} on {ticker} rejected. (Score {score:.2f} <= {self.threshold})")
             return True

        # Ex: If Short signal but sentiment is very positive -> Veto
        if direction == "Short" and score >= abs(self.threshold):
             logger.info(f"Sentiment Veto: {direction} on {ticker} rejected. (Score {score:.2f} >= {abs(self.threshold)})")
             return True

        # High Conviction (Optional: Could increase lot size if matching, but keeping simple for now)
        if (direction == "Long" and score > 0.2) or (direction == "Short" and score < -0.2):
             logger.info(f"High Conviction Signal: {direction} on {ticker} matches sentiment ({score:.2f}).")

        return False
