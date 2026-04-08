import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import feedparser
import asyncio
import logging

# Ensure VADER lexicon is downloaded
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

logger = logging.getLogger(__name__)

class SentimentEngine:
    """Phase 20: RSS Haber Duyarlılık Filtresi (NLTK VADER)"""
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.cache = {}
        # Simple RSS feeds mappings based on category (using free feeds)
        self.feeds = {
            "METALS": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "ENERGY": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "AGRI": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
            "FOREX": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
        }

    async def fetch_sentiment(self, category: str):
        """Asynchronously fetches news and calculates sentiment score."""
        url = self.feeds.get(category)
        if not url:
            return

        try:
            # Running synchronous feedparser in a thread to prevent blocking
            feed = await asyncio.to_thread(feedparser.parse, url)

            compound_scores = []
            for entry in feed.entries[:10]: # Check last 10 news
                score = self.sia.polarity_scores(entry.title)['compound']
                compound_scores.append(score)

            if compound_scores:
                avg_score = sum(compound_scores) / len(compound_scores)
                self.cache[category] = avg_score
                logger.info(f"Sentiment Updated for {category}: {avg_score:.2f}")
        except Exception as e:
            logger.warning(f"Failed to fetch sentiment for {category}: {e}")

    def get_sentiment_veto(self, direction: str, category: str) -> bool:
        """Returns True if sentiment heavily contradicts technical direction."""
        score = self.cache.get(category, 0.0)

        # If technical is LONG but news is strongly negative
        if direction == "LONG" and score < -0.30:
            logger.warning(f"Sentiment Veto! {category} LONG rejected (Score: {score:.2f})")
            return True

        # If technical is SHORT but news is strongly positive
        if direction == "SHORT" and score > 0.30:
            logger.warning(f"Sentiment Veto! {category} SHORT rejected (Score: {score:.2f})")
            return True

        return False
