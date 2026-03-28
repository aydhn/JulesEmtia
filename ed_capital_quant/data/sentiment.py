import feedparser
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import ssl
from utils.logger import log

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)

sia = SentimentIntensityAnalyzer()

def get_news_sentiment(asset_keyword: str) -> float:
    try:
        url = f"https://search.yahoo.com/mrss/?p={asset_keyword}"
        feed = feedparser.parse(url)
        scores = []
        for entry in feed.entries[:5]:
            score = sia.polarity_scores(entry.title)['compound']
            scores.append(score)
        return sum(scores)/len(scores) if scores else 0.0
    except Exception as e:
        log.error(f"Sentiment hatası ({asset_keyword}): {e}")
        return 0.0
