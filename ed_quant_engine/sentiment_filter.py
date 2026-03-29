import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
from typing import Dict, Any, List
from ed_quant_engine.logger import log

def _initialize_nltk():
    try:
        nltk.data.find('sentiment/vader_lexicon.zip')
    except LookupError:
        nltk.download('vader_lexicon', quiet=True)

_initialize_nltk()
sia = SentimentIntensityAnalyzer()

def fetch_rss_news() -> List[Dict[str, str]]:
    """Fetches free RSS news from Yahoo Finance/Investing for basic sentiment."""
    # Using multiple feeds to gather diverse headlines
    feeds = [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,DX-Y.NYB",
        "https://www.investing.com/rss/news_285.rss" # Commodities
    ]

    articles = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]: # Top 15 per feed
                articles.append({
                    "title": entry.title,
                    "summary": entry.summary if 'summary' in entry else entry.title,
                    "published": entry.published if 'published' in entry else ""
                })
        except Exception as e:
            log.warning(f"Failed to fetch RSS feed {url}: {e}")

    return articles

def analyze_sentiment(articles: List[Dict[str, str]], keywords: List[str]) -> float:
    """Calculates an average compound sentiment score for articles matching keywords."""
    if not articles:
        return 0.0

    relevant_scores = []
    for article in articles:
        text = (article["title"] + " " + article["summary"]).lower()
        if any(kw.lower() in text for kw in keywords):
            score = sia.polarity_scores(text)
            relevant_scores.append(score['compound'])

    if not relevant_scores:
        return 0.0 # Neutral if no relevant news

    avg_score = sum(relevant_scores) / len(relevant_scores)
    log.debug(f"Sentiment calculated for keywords {keywords}: {avg_score:.2f} across {len(relevant_scores)} articles.")
    return avg_score

def sentiment_veto(ticker: str, direction: str, articles: List[Dict[str, str]]) -> bool:
    """Returns True if the sentiment violently disagrees with the technical direction."""
    # Determine keywords based on ticker category
    keywords = ["economy", "fed", "inflation"]
    if "GC" in ticker or "SI" in ticker:
        keywords.extend(["gold", "silver", "metal", "yield"])
    elif "CL" in ticker or "BZ" in ticker:
        keywords.extend(["oil", "opec", "energy", "crude"])
    elif "TRY" in ticker:
        keywords.extend(["turkey", "lira", "cbrt", "erdogan"])

    score = analyze_sentiment(articles, keywords)

    # If the sentiment is very negative but technical says Long
    if direction == "Long" and score <= -0.50:
         log.info(f"Sentiment Veto: {ticker} Long blocked by {score:.2f} score.")
         return True

    # If the sentiment is very positive but technical says Short
    if direction == "Short" and score >= 0.50:
         log.info(f"Sentiment Veto: {ticker} Short blocked by {score:.2f} score.")
         return True

    return False

if __name__ == "__main__":
    news = fetch_rss_news()
    veto = sentiment_veto("GC=F", "Long", news)
    print("Veto:", veto)
