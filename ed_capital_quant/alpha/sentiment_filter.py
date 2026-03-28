import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from core.logger import setup_logger
from typing import List, Dict

logger = setup_logger("sentiment_filter")

# Ensure NLTK VADER lexicon is downloaded (only runs once)
try:
    nltk.data.find('vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class SentimentFilter:
    """
    Reads RSS news feeds and uses NLTK VADER to gauge market sentiment.
    Zero budget: Uses free financial RSS feeds.
    """
    def __init__(self):
        self.rss_urls = [
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", # WSJ Markets
            # "https://www.investing.com/rss/news_285.rss" # Investing.com Commodities
        ]
        self.analyzer = SentimentIntensityAnalyzer()
        self.cache: List[Dict] = []
        self.sentiment_threshold = -0.50 # Extremely negative threshold

    def fetch_and_analyze(self) -> float:
        """
        Fetches RSS feeds, analyzes headlines, and returns a composite sentiment score (-1 to 1).
        Negative score implies bad news (Risk-Off), positive implies good news (Risk-On).
        """
        logger.info("Fetching RSS news sentiment...")
        scores = []

        for url in self.rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]: # Top 10 headlines per feed
                    title = entry.title
                    sentiment = self.analyzer.polarity_scores(title)
                    scores.append(sentiment['compound'])
            except Exception as e:
                logger.error(f"Failed to fetch RSS from {url}: {e}")

        if not scores:
            return 0.0 # Neutral if failed

        avg_score = sum(scores) / len(scores)
        logger.info(f"Composite Sentiment Score: {avg_score:.2f}")
        return avg_score

    def validate_signal(self, direction: int, avg_score: float) -> bool:
        """
        Vetos Long signals if sentiment is extremely negative.
        Direction: 1 (Long), -1 (Short)
        """
        if direction == 1 and avg_score <= self.sentiment_threshold:
            logger.warning(f"Sentiment Veto: Refusing LONG due to extreme negative news (Score: {avg_score:.2f})")
            return False

        return True
