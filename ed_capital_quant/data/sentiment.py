import feedparser
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import ssl
from utils.logger import log
import time

# Resolve SSL cert issues in certain environments
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Ensure vader lexicon is available locally
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

# Basic in-memory cache to prevent spamming RSS feeds and blocking event loop
_sentiment_cache = {}

def get_news_sentiment(asset_keyword: str) -> float:
    current_time = time.time()

    # Check cache (valid for 1 hour)
    if asset_keyword in _sentiment_cache:
        cached_score, timestamp = _sentiment_cache[asset_keyword]
        if current_time - timestamp < 3600:
            return cached_score

    try:
        # Yahoo Finance RSS Feed
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={asset_keyword}"
        feed = feedparser.parse(url)
        scores = []

        for entry in feed.entries[:5]: # Analyze top 5 recent news
            score = sia.polarity_scores(entry.title)['compound']
            scores.append(score)

        final_score = sum(scores) / len(scores) if scores else 0.0

        # Update cache
        _sentiment_cache[asset_keyword] = (final_score, current_time)
        log.info(f"Sentiment for {asset_keyword}: {final_score:.2f}")
        return final_score

    except Exception as e:
        log.error(f"Sentiment hatası ({asset_keyword}): {e}")
        return 0.0
