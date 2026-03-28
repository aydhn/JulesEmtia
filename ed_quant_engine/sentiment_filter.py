import feedparser
import ssl
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from logger import get_logger

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

def analyze_sentiment(ticker: str, keywords: list) -> float:
    """
    Fetches RSS feeds, filters by keywords relating to the ticker/macro,
    and calculates an average VADER compound score (-1.0 to 1.0).
    Zero budget, local NLP processing.
    """
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
        return 0.0 # Neutral if no news found

    scores = [sia.polarity_scores(hl)['compound'] for hl in relevant_headlines]
    avg_score = sum(scores) / len(scores)

    log.info(f"Sentiment for {ticker}: {avg_score:.2f} from {len(relevant_headlines)} headlines.")
    return avg_score
