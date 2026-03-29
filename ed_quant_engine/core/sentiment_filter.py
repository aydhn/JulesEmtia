import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from typing import Dict, List, Any
import nltk
from ed_quant_engine.core.logger import logger
import threading

# Download the VADER lexicon if it's not present (do this once per container/environment)
try:
    nltk.download('vader_lexicon', quiet=True)
except Exception as e:
    logger.error(f"Failed to download vader_lexicon: {e}")

class SentimentFilter:
    """
    Zero-Budget NLP News Sentiment Analysis Engine using Yahoo Finance RSS and NLTK VADER.
    """
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.cache = {}
        self.rss_urls = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F", # Gold
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=CL=F", # Crude Oil
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=EURUSD=X", # General FX
            # Add more specific tickers as needed
        ]

    def update_sentiment_cache(self):
        """
        Runs asynchronously or in a thread. Fetches news and updates the cache.
        """
        logger.info("Starting background NLP sentiment update...")
        try:
            for url in self.rss_urls:
                ticker = url.split("s=")[-1]
                feed = feedparser.parse(url)

                scores = []
                for entry in feed.entries[:10]: # Top 10 headlines
                    text = f"{entry.title}. {entry.description}"
                    score = self.sia.polarity_scores(text)['compound']
                    scores.append(score)

                if scores:
                    avg_score = sum(scores) / len(scores)
                    self.cache[ticker] = avg_score
                    logger.debug(f"Sentiment cache updated for {ticker}: {avg_score:.2f}")
        except Exception as e:
            logger.error(f"Failed to update sentiment cache: {e}")

    def get_sentiment(self, ticker: str) -> float:
        """
        Returns the cached compound score (-1.0 to 1.0).
        If ticker not found, returns 0.0 (Neutral).
        """
        return self.cache.get(ticker, 0.0)

    def start_background_task(self, interval_minutes: int = 60):
        """
        Uses Python threading to poll RSS feeds without blocking the main event loop.
        """
        def run():
            import time
            while True:
                self.update_sentiment_cache()
                time.sleep(interval_minutes * 60)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

sentiment_filter = SentimentFilter()
