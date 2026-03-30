import feedparser
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
import asyncio
from logger import logger

# Initialize NLTK VADER once
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

class SentimentFilter:
    """
    Zero-budget NLP Sentiment Analysis Engine (Phase 20).
    Reads RSS feeds to gauge market sentiment and filter false technical signals.
    """

    # Trusted Free RSS Feeds
    RSS_FEEDS = {
        "Investing_Commodities": "https://www.investing.com/rss/news_11.rss",
        "Investing_Forex": "https://www.investing.com/rss/news_1.rss",
        "Yahoo_Finance_Top": "https://finance.yahoo.com/news/rssindex"
    }

    # Asset to Keyword Mapping for targeted sentiment
    ASSET_KEYWORDS = {
        "Gold": ["gold", "bullion", "xau", "precious metal"],
        "Silver": ["silver", "xag"],
        "Oil": ["oil", "crude", "wti", "brent", "opec"],
        "USD": ["dollar", "fed", "powell", "inflation", "cpi", "dxy"],
        "TRY": ["lira", "tcmb", "cbrt", "turkey"]
    }

    @classmethod
    async def fetch_and_analyze(cls, ticker_name: str) -> float:
        """
        Asynchronously fetches news and calculates average VADER compound score (-1.0 to 1.0)
        for a specific asset based on keywords.
        """
        logger.info(f"Running NLP Sentiment Analysis for {ticker_name}...")

        # Determine relevant keywords for the ticker
        keywords = []
        for key, words in cls.ASSET_KEYWORDS.items():
            if key.lower() in ticker_name.lower():
                keywords.extend(words)

        # If no specific keywords match, use general macro keywords
        if not keywords:
            keywords = ["economy", "inflation", "recession", "markets"]

        total_score = 0.0
        relevant_articles = 0

        try:
            # Parse feeds asynchronously to prevent blocking
            for feed_url in cls.RSS_FEEDS.values():
                feed = await asyncio.to_thread(feedparser.parse, feed_url)

                for entry in feed.entries:
                    title = entry.title.lower()
                    summary = entry.get('summary', '').lower()

                    # Check if any keyword is in title or summary
                    if any(kw in title or kw in summary for kw in keywords):
                        # Calculate VADER sentiment
                        score = sia.polarity_scores(entry.title)['compound']
                        total_score += score
                        relevant_articles += 1

            # Return average sentiment score
            if relevant_articles > 0:
                avg_score = total_score / relevant_articles
                logger.info(f"Sentiment for {ticker_name}: {avg_score:.2f} (Based on {relevant_articles} articles)")
                return avg_score
            else:
                logger.debug(f"No relevant news found for {ticker_name}.")
                return 0.0

        except Exception as e:
            logger.error(f"Error fetching RSS feeds for NLP: {e}")
            return 0.0

    @classmethod
    async def check_sentiment_veto(cls, ticker_name: str, signal_direction: int, threshold: float = 0.50) -> bool:
        """
        Checks if the fundamental sentiment contradicts the technical signal.
        Returns True if signal should be VETOED.
        signal_direction: 1 (Long) or -1 (Short)
        """
        sentiment_score = await cls.fetch_and_analyze(ticker_name)

        # If signal is LONG (1) but sentiment is intensely NEGATIVE (<-0.50) -> VETO
        if signal_direction == 1 and sentiment_score < -threshold:
            logger.warning(f"SENTIMENT VETO: Technical Long for {ticker_name} rejected due to negative news ({sentiment_score:.2f}).")
            return True

        # If signal is SHORT (-1) but sentiment is intensely POSITIVE (>0.50) -> VETO
        if signal_direction == -1 and sentiment_score > threshold:
            logger.warning(f"SENTIMENT VETO: Technical Short for {ticker_name} rejected due to positive news ({sentiment_score:.2f}).")
            return True

        # Confluence / High Conviction
        if (signal_direction == 1 and sentiment_score > threshold) or (signal_direction == -1 and sentiment_score < -threshold):
            logger.info(f"HIGH CONVICTION: Technical and Fundamental confluence for {ticker_name} (Sentiment: {sentiment_score:.2f}).")

        return False
