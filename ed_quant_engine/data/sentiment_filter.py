import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from core.logger import get_logger

logger = get_logger()

class SentimentFilter:
    def __init__(self):
        self.download_vader()
        self.analyzer = SentimentIntensityAnalyzer()
        # Free Yahoo Finance RSS News Feeds
        self.rss_feeds = {
            "economy": "https://finance.yahoo.com/news/rssindex",
            "commodities": "https://finance.yahoo.com/news/commodities/rss",
            "forex": "https://finance.yahoo.com/news/currencies/rss"
        }
        self.cache = {}

    def download_vader(self):
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            logger.info("Downloading NLTK VADER lexicon...")
            nltk.download('vader_lexicon', quiet=True)

    def get_news_sentiment(self, category: str = "economy") -> float:
        """Fetches latest RSS news and returns average VADER compound score."""
        url = self.rss_feeds.get(category, self.rss_feeds["economy"])

        try:
            feed = feedparser.parse(url)
            if not feed.entries: return 0.0

            total_score = 0.0
            count = 0

            for entry in feed.entries[:15]: # Analyze top 15 news
                text = entry.title + " " + entry.summary
                score = self.analyzer.polarity_scores(text)['compound']
                total_score += score
                count += 1

            avg_score = total_score / count if count > 0 else 0.0
            self.cache[category] = avg_score
            return avg_score

        except Exception as e:
            logger.error(f"RSS Parsing Error ({category}): {e}")
            return 0.0
