from __future__ import annotations

import asyncio

import feedparser

from src.logger import get_logger


logger = get_logger()
_SIA = None
_SIA_UNAVAILABLE = False


def _get_sentiment_analyzer():
    global _SIA, _SIA_UNAVAILABLE
    if _SIA or _SIA_UNAVAILABLE:
        return _SIA
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer

        _SIA = SentimentIntensityAnalyzer()
        return _SIA
    except LookupError:
        logger.warning("NLTK vader_lexicon is not available. Sentiment veto will stay neutral.")
        _SIA_UNAVAILABLE = True
        return None
    except Exception as exc:
        logger.warning("Sentiment analyzer unavailable: %s", exc)
        _SIA_UNAVAILABLE = True
        return None


async def fetch_rss_sentiment(query: str = "markets") -> float:
    """
    Reads Yahoo Finance RSS via feedparser and returns average VADER sentiment.
    If RSS or local NLTK resources fail, returns neutral 0.0.
    """
    try:
        feed = await asyncio.to_thread(feedparser.parse, "https://finance.yahoo.com/news/rssindex")
        if not feed.entries:
            return 0.0
        analyzer = _get_sentiment_analyzer()
        if analyzer is None:
            return 0.0
        scores = [analyzer.polarity_scores(entry.title)["compound"] for entry in feed.entries[:10]]
        return sum(scores) / len(scores) if scores else 0.0
    except Exception as exc:
        logger.warning("RSS sentiment unavailable: %s", exc)
        return 0.0
