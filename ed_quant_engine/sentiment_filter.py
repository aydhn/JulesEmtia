import feedparser
import ssl
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from logger import get_logger
import time

# Bypass SSL verification for legacy feeds
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

log = get_logger()

# Download VADER lexicon silently
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml" # WSJ Markets
]

# Simple in-memory cache to prevent spamming RSS feeds and getting banned (Phase 20 logic optimization)
SENTIMENT_CACHE = {}
CACHE_TTL = 3600 # 1 hour

def analyze_sentiment(ticker: str, keywords: list) -> float:
    """
    Fetches RSS feeds, filters by keywords relating to the ticker/macro,
    and calculates an average VADER compound score (-1.0 to 1.0).
    Zero budget, local NLP processing.
    Includes caching to prevent rate-limiting.
    """
    cache_key = ticker
    now = time.time()

    if cache_key in SENTIMENT_CACHE:
        cached_score, timestamp = SENTIMENT_CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            log.info(f"Using cached sentiment for {ticker}: {cached_score:.2f}")
            return cached_score

    relevant_headlines = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]: # Top 20 per feed
                title = entry.title.lower()
                if any(kw.lower() in title for kw in keywords):
                    relevant_headlines.append(entry.title)
        except Exception as e:
            log.warning(f"Error parsing RSS {feed_url}: {e}")

    if not relevant_headlines:
        SENTIMENT_CACHE[cache_key] = (0.0, now)
        return 0.0 # Neutral if no news found

    scores = [sia.polarity_scores(hl)['compound'] for hl in relevant_headlines]
    avg_score = sum(scores) / len(scores)

    SENTIMENT_CACHE[cache_key] = (avg_score, now)
    log.info(f"Sentiment for {ticker}: {avg_score:.2f} from {len(relevant_headlines)} headlines.")
    return avg_score
