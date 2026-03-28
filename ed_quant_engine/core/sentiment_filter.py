import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from ed_quant_engine.utils.logger import setup_logger

logger = setup_logger("SentimentFilter")

# Download VADER lexicon on first run silently
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class SentimentFilter:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        self.rss_urls = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,DX-Y.NYB",
            # Add more free RSS feeds here
        ]
        self.cache = {}

    def fetch_news_sentiment(self) -> float:
        """Fetches RSS news and calculates aggregate sentiment score (-1 to 1)."""
        try:
            compound_scores = []
            for url in self.rss_urls:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]: # Top 10 latest
                    score = self.sia.polarity_scores(entry.title)['compound']
                    compound_scores.append(score)

            if not compound_scores:
                 return 0.0

            avg_score = sum(compound_scores) / len(compound_scores)
            self.cache['macro_sentiment'] = avg_score
            logger.info(f"Updated Macro Sentiment Score: {avg_score:.2f}")
            return avg_score

        except Exception as e:
            logger.error(f"Failed to fetch RSS sentiment: {e}")
            return 0.0

    def veto_signal(self, direction: str, threshold=0.5) -> bool:
        """Returns True if sentiment strongly contradicts the technical signal."""
        score = self.cache.get('macro_sentiment', 0.0)

        if direction == "Long" and score <= -threshold:
             logger.warning(f"Sentiment Veto: Negative news ({score:.2f}) blocks Long.")
             return True
        elif direction == "Short" and score >= threshold:
             logger.warning(f"Sentiment Veto: Positive news ({score:.2f}) blocks Short.")
             return True

        return False
