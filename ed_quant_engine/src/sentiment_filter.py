import feedparser
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from .logger import log_info, log_warning, log_error

try:
    sia = SentimentIntensityAnalyzer()
except LookupError:
    import nltk
    nltk.download('vader_lexicon')
    sia = SentimentIntensityAnalyzer()

# SIFIR BÜTÇE RSS Feed URL'leri
RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,USDTRY=X",
    "https://www.investing.com/rss/news_285.rss" # Emtia
]

def fetch_rss_sentiment(keyword: str) -> float:
    """
    Belirlenen anahtar kelime (Altın, Oil vs.) ile RSS'den haberleri çeker ve
    VADER Sentiment Analysis ile compound (karma) duyarlılık skorunu döner.
    (-1.0 En Negatif, +1.0 En Pozitif)
    """
    total_score = 0.0
    count = 0

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if keyword.lower() in entry.title.lower() or keyword.lower() in entry.summary.lower():
                    sentiment = sia.polarity_scores(entry.title)
                    total_score += sentiment['compound']
                    count += 1
        except Exception as e:
            log_error(f"RSS Hatası ({url}): {e}")

    if count == 0:
        return 0.0

    avg_score = total_score / count
    log_info(f"[{keyword}] NLP Duyarlılık Skoru (Sentiment): {avg_score:.2f} ({count} haber incelendi)")
    return avg_score

def check_sentiment_veto(ticker: str, direction: str, threshold: float = -0.50) -> bool:
    """
    Eğer teknik gösterge Long (Al) diyor, ancak haber duyarlılığı felaket negatifse
    (-0.50'den küçükse) vetoyu basar (True döner).
    """
    # Basit anahtar kelime haritalaması
    keyword = "Market"
    if "GC=F" in ticker: keyword = "Gold"
    elif "CL=F" in ticker: keyword = "Oil"
    elif "TRY" in ticker: keyword = "Lira"

    sentiment_score = fetch_rss_sentiment(keyword)

    # Haberler felaket kötüyken ALIM (Long) yapma
    if direction == "Long" and sentiment_score < threshold:
        log_warning(f"🚨 SENTIMENT VETOSU: [{ticker}] Haberler {keyword} için felaket negatif. ({sentiment_score:.2f})")
        return True

    # Haberler harikayken SATIŞ (Short) yapma
    if direction == "Short" and sentiment_score > abs(threshold):
        log_warning(f"🚨 SENTIMENT VETOSU: [{ticker}] Haberler {keyword} için çok olumlu. ({sentiment_score:.2f})")
        return True

    return False
