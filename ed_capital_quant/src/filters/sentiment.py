import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from src.core.logger import logger
from src.core.config import SENTIMENT_THRESHOLD
import threading
import time
from collections import defaultdict

class RSSSentimentFilter:
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.rss_urls = [
            "https://finance.yahoo.com/news/rssindex",
            "https://www.investing.com/rss/news_285.rss" # Commodities/Forex news
        ]
        self.cache = defaultdict(list)
        self.keywords = {
            "Metals": ["gold", "silver", "copper", "metal", "precious"],
            "Energy": ["oil", "brent", "crude", "energy", "gas"],
            "Forex_TRY": ["lira", "try", "turkey", "cbrt", "inflation"],
            "Agriculture": ["wheat", "corn", "coffee", "sugar", "agriculture"]
        }

    def _fetch_feeds(self):
        """Fetches RSS feeds and caches them in memory."""
        try:
            logger.info("Fetching RSS Feeds for Sentiment Analysis...")
            new_cache = defaultdict(list)
            for url in self.rss_urls:
                feed = feedparser.parse(url)
                for entry in feed.entries[:20]: # Top 20 news
                    title = entry.title.lower()
                    summary = getattr(entry, 'summary', '').lower()
                    text = f"{title} {summary}"

                    score = self.analyzer.polarity_scores(text)['compound']

                    # Categorize news by keyword match
                    for category, words in self.keywords.items():
                        if any(word in text for word in words):
                            new_cache[category].append(score)

            # Calculate average sentiment per category
            for category, scores in new_cache.items():
                if scores:
                    self.cache[category] = sum(scores) / len(scores)
            logger.info(f"Sentiment Cache Updated: {dict(self.cache)}")
        except Exception as e:
            logger.error(f"Error fetching RSS feeds: {e}")

    def update_sentiment_async(self):
        """Runs feed fetching in a background thread."""
        thread = threading.Thread(target=self._fetch_feeds, daemon=True)
        thread.start()

    def validate_sentiment(self, category: str, direction: str) -> bool:
        """
        Validates technical signal against sentiment.
        Vetoes Long if sentiment is severely negative.
        Vetoes Short if sentiment is severely positive.
        """
        score = self.cache.get(category, 0.0)

        if direction == "Long" and score < SENTIMENT_THRESHOLD:
            logger.info(f"Sentiment Veto: {category} Long signal blocked by negative sentiment ({score:.2f})")
            return False
        elif direction == "Short" and score > abs(SENTIMENT_THRESHOLD):
            logger.info(f"Sentiment Veto: {category} Short signal blocked by positive sentiment ({score:.2f})")
            return False

        logger.debug(f"Sentiment Confluence: {category} {direction} allowed (Score: {score:.2f})")
        return True
