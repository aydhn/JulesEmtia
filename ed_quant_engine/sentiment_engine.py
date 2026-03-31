import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from logger import get_logger

logger = get_logger("sentiment_engine")

# Try to download VADER lexicon if missing
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class SentimentAnalyzer:
    """NLP News Sentiment Filter using NLTK VADER and free RSS feeds."""
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.rss_feeds = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,SI=F,CL=F,DX-Y.NYB",
            # Can add investing.com or other generic finance RSS feeds here
        ]

    def _fetch_headlines(self) -> list:
        headlines = []
        for url in self.rss_feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]: # Get top 10 latest
                    headlines.append(entry.title)
            except Exception as e:
                logger.error(f"Failed fetching RSS feed {url}: {e}")
        return headlines

    def get_market_sentiment(self, asset_keywords: list = None) -> float:
        """
        Analyzes recent headlines and returns a compound sentiment score (-1 to 1).
        If asset_keywords are provided, filters headlines for those words.
        """
        headlines = self._fetch_headlines()
        if not headlines:
            return 0.0

        filtered_headlines = headlines
        if asset_keywords:
            filtered_headlines = [
                h for h in headlines
                if any(kw.lower() in h.lower() for kw in asset_keywords)
            ]

        if not filtered_headlines:
            return 0.0 # Neutral if no relevant news

        scores = [self.sia.polarity_scores(h)['compound'] for h in filtered_headlines]
        avg_score = sum(scores) / len(scores)

        logger.info(f"Sentiment Score for {asset_keywords if asset_keywords else 'Market'}: {avg_score:.2f} based on {len(filtered_headlines)} headlines.")
        return avg_score
