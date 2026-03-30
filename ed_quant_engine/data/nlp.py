import feedparser
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from core.logger import get_logger

# Initialize NLTK
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

log = get_logger()
sia = SentimentIntensityAnalyzer()

def get_news_sentiment(keyword: str) -> float:
    # Example RSS feed for testing (using general finance feeds)
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY"

    # Note: In a real system you'd use specific RSS feeds per asset, e.g. "GC=F"
    try:
        feed = feedparser.parse(url)
        scores = []
        for entry in feed.entries[:10]: # Check last 10 news
            if keyword.lower() in entry.title.lower() or keyword.lower() in entry.summary.lower():
                score = sia.polarity_scores(entry.title)['compound']
                scores.append(score)

        if scores:
            avg_score = sum(scores) / len(scores)
            log.info(f"NLP Sentiment for {keyword}: {avg_score:.2f}")
            return avg_score
    except Exception as e:
        log.error(f"RSS Fetch Error: {e}")

    return 0.0 # Neutral if no news found
