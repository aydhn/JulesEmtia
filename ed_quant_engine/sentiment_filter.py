import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from typing import Dict, Optional
from logger import log
import time

# Download VADER lexicon if not present (only done once)
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()

# Basic mapping of tickers to keywords for filtering
TICKER_KEYWORDS = {
    "GC=F": ["gold", "precious metals", "safe haven"],
    "SI=F": ["silver", "precious metals"],
    "CL=F": ["oil", "crude", "energy", "opec"],
    "USDTRY=X": ["lira", "turkey", "cbrt", "emerging markets"]
    # ... expand as needed
}

def analyze_sentiment(ticker: str) -> float:
    """
    Fetches latest RSS feeds related to the ticker and calculates
    an average compound sentiment score (-1 to 1).
    """
    rss_urls = [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC", # General market
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}" # Specific ticker
    ]

    keywords = TICKER_KEYWORDS.get(ticker, [])

    total_score = 0.0
    count = 0

    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]: # Check last 10 articles
                title = entry.title.lower()

                # If keywords defined, skip articles not containing them
                if keywords and not any(kw in title for kw in keywords):
                    continue

                score = sia.polarity_scores(entry.title)['compound']
                total_score += score
                count += 1

        except Exception as e:
            log.warning(f"Error parsing RSS feed for {ticker}: {e}")

    if count == 0:
        return 0.0 # Neutral if no relevant news

    avg_score = total_score / count
    log.info(f"Sentiment Score for {ticker}: {avg_score:.2f} (based on {count} articles)")
    return avg_score
