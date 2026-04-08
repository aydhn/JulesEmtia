import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import asyncio
from typing import Dict
from .logger import quant_logger

class NLPSentimentFilter:
    def __init__(self):
        self.sia = SentimentIntensityAnalyzer()
        # RSS Feeds (Yahoo Finance general + Commodities)
        self.feeds = [
            "https://finance.yahoo.com/news/rssindex",
            "https://www.investing.com/rss/news_11.rss" # Commodities
        ]
        self.keywords = {
            "Gold": ["gold", "xau", "bullion"],
            "Oil": ["oil", "wti", "brent", "crude", "opec"],
            "Forex": ["fed", "inflation", "rates", "dollar", "powell", "cpi"],
        }
        self.sentiment_cache = {}

    async def _fetch_feed(self, url: str) -> list:
        try:
            feed = await asyncio.to_thread(feedparser.parse, url)
            return feed.entries
        except Exception as e:
            quant_logger.error(f"RSS fetch failed for {url}: {e}")
            return []

    async def get_market_sentiment(self) -> Dict[str, float]:
        """
        Reads RSS feeds, scores headlines via VADER, aggregates by category.
        Returns a dict of sentiment scores (-1.0 to 1.0)
        """
        sentiment_scores = {"Gold": 0.0, "Oil": 0.0, "Forex": 0.0}
        counts = {"Gold": 0, "Oil": 0, "Forex": 0}

        tasks = [self._fetch_feed(url) for url in self.feeds]
        all_entries = await asyncio.gather(*tasks)

        for entries in all_entries:
            for entry in entries:
                title = entry.title.lower()
                score = self.sia.polarity_scores(title)['compound']

                for category, words in self.keywords.items():
                    if any(w in title for w in words):
                        sentiment_scores[category] += score
                        counts[category] += 1

        # Average the scores
        for category in sentiment_scores:
            if counts[category] > 0:
                sentiment_scores[category] /= counts[category]

        self.sentiment_cache = sentiment_scores
        quant_logger.info(f"NLP Sentiment Updated: {sentiment_scores}")
        return sentiment_scores

    def veto_signal(self, ticker: str, direction: str) -> bool:
        """
        Phase 20: Vetos a signal if the sentiment is heavily against it.
        """
        category = "Forex"
        if "GC=F" in ticker or "SI=F" in ticker: category = "Gold"
        if "CL=F" in ticker or "BZ=F" in ticker: category = "Oil"

        score = self.sentiment_cache.get(category, 0.0)

        if direction == "Long" and score <= -0.5:
            quant_logger.warning(f"Sentiment Veto: Rejected Long on {ticker} due to extremely negative news ({score}).")
            return True
        if direction == "Short" and score >= 0.5:
            quant_logger.warning(f"Sentiment Veto: Rejected Short on {ticker} due to extremely positive news ({score}).")
            return True

        return False
