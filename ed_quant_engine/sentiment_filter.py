import feedparser
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from typing import Dict, Optional

from logger import log

# Download NLTK VADER lexicon if not present
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()

# Free RSS feeds related to Commodities and Macro
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", # WSJ Markets
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=100003114" # CNBC Finance
]

# Simple caching mechanism to avoid slow API fetching on every 1H cycle
_SENTIMENT_CACHE: Dict[str, float] = {}

def update_sentiment_cache() -> None:
    """
    Parses RSS feeds, calculates VADER compound scores, and caches
    the aggregated market sentiment (-1.0 to +1.0).
    """
    try:
        total_score = 0.0
        articles_scored = 0

        for url in RSS_FEEDS:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]: # Check last 10 headlines per feed
                title = entry.title
                summary = entry.get('summary', '')
                text = f"{title} {summary}"

                # Filter out irrelevant news using basic keywords
                keywords = ['gold', 'oil', 'fed', 'inflation', 'rates', 'yield', 'currency', 'dollar']
                if any(kw in text.lower() for kw in keywords):
                    score = sia.polarity_scores(text)['compound']
                    total_score += score
                    articles_scored += 1

        if articles_scored > 0:
            avg_score = total_score / articles_scored
            _SENTIMENT_CACHE['macro'] = avg_score
            log.info(f"Sentiment Cache Updated: {articles_scored} articles, Score: {avg_score:.2f}")
        else:
            _SENTIMENT_CACHE['macro'] = 0.0
            log.info("No relevant articles found for sentiment update.")

    except Exception as e:
        log.error(f"Failed to update RSS sentiment: {e}")

def get_macro_sentiment() -> float:
    """Returns the cached sentiment score."""
    return _SENTIMENT_CACHE.get('macro', 0.0)

def validate_sentiment(ticker: str, signal_direction: str, threshold: float = 0.20) -> bool:
    """
    NLP Filter: Rejects trades if the underlying news sentiment strongly contradicts the technical signal.
    """
    score = get_macro_sentiment()

    # If the signal is Long, but the news is extremely negative
    if signal_direction == "Long" and score < -threshold:
        log.warning(f"Sentiment Veto: {ticker} Technicals are Long, but News is Negative ({score:.2f})")
        return False

    # If the signal is Short, but the news is extremely positive
    elif signal_direction == "Short" and score > threshold:
        log.warning(f"Sentiment Veto: {ticker} Technicals are Short, but News is Positive ({score:.2f})")
        return False

    return True

