import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from src.logger import get_logger

logger = get_logger("sentiment_filter")

# Download NLTK VADER lexicon if not present (handled once at startup)
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon')

sia = SentimentIntensityAnalyzer()

# Free RSS feeds for financial news
RSS_FEEDS = [
    "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", # WSJ Markets
]

def analyze_sentiment(query: str = "") -> float:
    """Fetches RSS news and returns an aggregated sentiment compound score (-1.0 to 1.0)."""
    compound_scores = []

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]: # Parse latest 20 news items
                text = f"{entry.title} {entry.summary if 'summary' in entry else ''}"
                if query.lower() in text.lower() or query == "":
                    score = sia.polarity_scores(text)['compound']
                    compound_scores.append(score)
        except Exception as e:
            logger.error(f"RSS Parsing error from {url}: {e}")

    if not compound_scores:
        return 0.0 # Neutral if no relevant news found

    avg_score = sum(compound_scores) / len(compound_scores)
    return avg_score

def check_sentiment_veto(ticker: str, signal: str) -> bool:
    """Returns True if news sentiment strongly contradicts the technical signal."""
    # Mapping tickers to basic search keywords
    kw_map = {
        "GC=F": "gold", "SI=F": "silver", "CL=F": "oil", "USDTRY=X": "turkey", "EURTRY=X": "europe"
    }

    keyword = kw_map.get(ticker, "economy")
    score = analyze_sentiment(keyword)

    # If technicals say Buy, but news is extremely negative
    if signal == "Long" and score < -0.40:
        logger.info(f"Sentiment Veto: Rejected {signal} for {ticker}. Score: {score:.2f}")
        return True

    # If technicals say Sell, but news is extremely positive
    if signal == "Short" and score > 0.40:
        logger.info(f"Sentiment Veto: Rejected {signal} for {ticker}. Score: {score:.2f}")
        return True

    return False
