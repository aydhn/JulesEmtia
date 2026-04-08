import feedparser
import asyncio
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from src.logger import get_logger
import nltk

logger = get_logger()

# Ensure vader is downloaded once
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

async def fetch_rss_sentiment(query: str = "markets") -> float:
    """
    Fetches RSS feed (e.g. Yahoo Finance) and calculates average VADER sentiment.
    Zero budget: Uses feedparser instead of paid APIs.
    """
    url = f"https://finance.yahoo.com/news/rssindex"
    try:
        # Run synchronous feedparser in a thread
        feed = await asyncio.to_thread(feedparser.parse, url)
        if not feed.entries:
            return 0.0

        sia = SentimentIntensityAnalyzer()
        scores = []
        for entry in feed.entries[:10]:  # Analyze top 10 news
            # Basic keyword filtering can be added here
            score = sia.polarity_scores(entry.title)['compound']
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        return avg_score
    except Exception as e:
        logger.error(f"Error fetching RSS sentiment: {e}")
        return 0.0
