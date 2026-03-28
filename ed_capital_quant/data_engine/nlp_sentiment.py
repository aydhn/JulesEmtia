import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import logging
from typing import Dict, List
from datetime import datetime, timedelta
import asyncio
import concurrent.futures

from core.logger import logger

try:
    nltk.data.find('sentiment/vader_lexicon')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

class NLPSentimentFilter:
    """Ücretsiz RSS beslemeleri üzerinden VADER ile Haber Duyarlılık Analizi (Asenkron Çekim)."""

    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        self.rss_feeds = [
            "https://finance.yahoo.com/news/rssindex",
            "https://www.cnbc.com/id/10000664/device/rss/rss.html"
        ]
        self.cache = {}
        self.last_fetch_time = None

    def _sync_fetch(self) -> List[Dict]:
        """İçeriden çağırılan senkron RSS çekim aracı (ThreadPoolExecutor ile sarmalanacak)."""
        news_items = []
        now = datetime.now()

        for url in self.rss_feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    if hasattr(entry, 'published_parsed'):
                        pub_time = datetime(*entry.published_parsed[:6])
                        if now - pub_time > timedelta(hours=12):
                            continue

                    news_items.append({
                        "title": entry.title,
                        "summary": getattr(entry, 'summary', ''),
                        "link": getattr(entry, 'link', '')
                    })
            except Exception as e:
                logger.error(f"RSS Çekme Hatası ({url}): {e}")

        return news_items

    async def _fetch_and_parse_news_async(self) -> List[Dict]:
        """RSS beslemelerini non-blocking olarak Thread Pool üzerinden çeker."""
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            news_items = await loop.run_in_executor(pool, self._sync_fetch)
        return news_items

    async def update_cache_async(self):
        """Asenkron olarak haber önbelleğini yeniler."""
        now = datetime.now()
        if not self.last_fetch_time or (now - self.last_fetch_time > timedelta(hours=1)):
            logger.info("RSS Haberleri güncelleniyor (Asenkron NLP Analizi).")
            self.cache["global_news"] = await self._fetch_and_parse_news_async()
            self.last_fetch_time = now

    def calculate_sentiment_score(self, ticker: str, keywords: List[str] = []) -> float:
        """Belirli bir varlık için haber başlıklarındaki ortalama duyarlılığı hesaplar (Cache'den okur)."""
        all_news = self.cache.get("global_news", [])
        if not all_news:
            return 0.0 # Nötr

        relevant_news = []
        for news in all_news:
            text = f"{news['title']} {news['summary']}".lower()
            if ticker.lower() in text or any(k.lower() in text for k in keywords):
                relevant_news.append(text)

        if not relevant_news:
            return 0.0

        total_score = sum(self.analyzer.polarity_scores(text)['compound'] for text in relevant_news)
        avg_score = total_score / len(relevant_news)

        logger.info(f"[{ticker}] NLP Duyarlılık Skoru: {avg_score:.2f} (Örneklem: {len(relevant_news)} haber)")
        return avg_score

    async def sentiment_veto_async(self, ticker: str, direction: str, threshold: float = 0.50) -> bool:
        """
        Eğer teknik sinyal ile haber duyarlılığı tamamen zıt ise True (Veto) döndürür.
        Önce önbelleği yeniler (asenkron), sonra hesaplar.
        """
        await self.update_cache_async() # Non-blocking cache update

        keywords = []
        if "Gold" in ticker or "Silver" in ticker:
            keywords = ["precious", "inflation", "fed", "rates"]
        elif "Oil" in ticker or "Gas" in ticker:
            keywords = ["opec", "energy", "supply", "demand"]
        elif "TRY" in ticker:
            keywords = ["turkey", "cbrt", "lira", "inflation", "erdogan"]

        score = self.calculate_sentiment_score(ticker, keywords)

        if direction == "Long" and score <= -threshold:
            logger.warning(f"SENTIMENT VETO: [{ticker}] Teknik sinyal Long, ancak haberler çok Negatif ({score:.2f})")
            return True
        elif direction == "Short" and score >= threshold:
            logger.warning(f"SENTIMENT VETO: [{ticker}] Teknik sinyal Short, ancak haberler çok Pozitif ({score:.2f})")
            return True

        return False