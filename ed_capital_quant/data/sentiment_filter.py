import feedparser
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from core.logger import logger

try:
    nltk.download('vader_lexicon', quiet=True)
except:
    pass

class SentimentFilter:
    def __init__(self):
        try:
            self.sia = SentimentIntensityAnalyzer()
        except:
            self.sia = None
        self.rss_urls = ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=GLD,USO,UUP"]

    def get_market_sentiment(self) -> float:
        if not self.sia:
            return 0.0
        compound_scores = []
        for url in self.rss_urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    score = self.sia.polarity_scores(entry.title)['compound']
                    compound_scores.append(score)
            except:
                pass

        avg_score = sum(compound_scores)/len(compound_scores) if compound_scores else 0
        logger.info(f"NLP Market Duyarlılığı (VADER): {avg_score:.2f}")
        return avg_score
