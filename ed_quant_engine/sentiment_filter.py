import feedparser
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from logger import logger

# Phase 20: NLP Download
try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class SentimentFilter:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        # Free RSS feeds
        self.rss_urls = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,SI=F,CL=F,USDTRY=X",
            "https://www.investing.com/rss/news_285.rss" # Commodities
        ]
        self.cache = {}

    async def fetch_news(self):
        try:
            articles = []
            for url in self.rss_urls:
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]: # Get top 10
                    articles.append({
                        'title': entry.title,
                        'summary': entry.get('summary', '')
                    })

            self._analyze_sentiment(articles)
        except Exception as e:
            logger.error(f"RSS fetch error: {e}")

    def _analyze_sentiment(self, articles):
        if not articles: return

        scores = []
        for article in articles:
            text = f"{article['title']} {article['summary']}"
            score = self.sia.polarity_scores(text)
            scores.append(score['compound'])

        avg_score = sum(scores) / len(scores) if scores else 0
        self.cache['global_sentiment'] = avg_score
        logger.info(f"Global Sentiment Score updated: {avg_score:.2f}")

    def veto_signal(self, ticker: str, direction: str) -> bool:
        '''
        Phase 20: Sentiment Veto
        '''
        if 'global_sentiment' not in self.cache:
            return False

        score = self.cache['global_sentiment']

        # If extreme negative news (-0.5), veto Longs
        if score < -0.5 and direction == "Long":
            logger.info(f"Sentiment Veto: {direction} {ticker} rejected. Extremely negative news flow ({score:.2f}).")
            return True
        # If extreme positive news (+0.5), veto Shorts
        elif score > 0.5 and direction == "Short":
            logger.info(f"Sentiment Veto: {direction} {ticker} rejected. Extremely positive news flow ({score:.2f}).")
            return True

        return False

sentiment_filter = SentimentFilter()