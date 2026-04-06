import feedparser
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger("SentimentFilter")

# Ensure NLTK lexicons are downloaded silently
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class SentimentAnalyzer:
    """Uses NLTK VADER to analyze financial news RSS feeds for market sentiment."""

    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        # RSS Feeds (Free sources)
        self.feeds = [
            "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", # Finance
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml" # WSJ Markets
        ]

    def fetch_and_analyze(self, keywords: list) -> float:
        """Fetches RSS headlines, filters by keywords, and calculates average sentiment score."""
        scores = []
        try:
            for feed_url in self.feeds:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title = entry.title
                    # Check if relevant keywords exist in title
                    if any(kw.lower() in title.lower() for kw in keywords):
                        # Calculate VADER compound score (-1.0 to 1.0)
                        score = self.sia.polarity_scores(title)['compound']
                        scores.append(score)

            if not scores:
                return 0.0 # Neutral if no news found

            avg_score = sum(scores) / len(scores)
            logger.info(f"Haber Duyarlılık Skoru (Sentiment): {avg_score:.2f} (Örneklem: {len(scores)})")
            return avg_score

        except Exception as e:
            logger.error(f"Duyarlılık analizi hatası: {str(e)}")
            return 0.0

def analyze_news_sentiment() -> SentimentAnalyzer:
    return SentimentAnalyzer()

def check_sentiment_veto(ticker: str, direction: str, analyzer: SentimentAnalyzer) -> bool:
    """Blocks a signal if the overall market sentiment is strongly against the technical direction."""
    # Map ticker to search keywords
    keywords_map = {
        "GC=F": ["gold", "precious metals", "inflation", "fed"],
        "CL=F": ["oil", "energy", "opec", "crude"],
        "USDTRY=X": ["lira", "turkey", "inflation", "central bank"]
    }

    # Default to general macro terms if ticker specific not found
    keywords = keywords_map.get(ticker, ["markets", "economy", "fed", "inflation"])

    score = analyzer.fetch_and_analyze(keywords)

    # Thresholds
    NEGATIVE_THRESHOLD = -0.5
    POSITIVE_THRESHOLD = 0.5

    # Veto logic
    if direction == "Long" and score < NEGATIVE_THRESHOLD:
        logger.warning(f"Sentiment Vetosu: {ticker} (Long) reddedildi. Şiddetli Negatif Duyarlılık ({score:.2f})")
        return True # VETO

    if direction == "Short" and score > POSITIVE_THRESHOLD:
        logger.warning(f"Sentiment Vetosu: {ticker} (Short) reddedildi. Şiddetli Pozitif Duyarlılık ({score:.2f})")
        return True # VETO

    return False # Pass
