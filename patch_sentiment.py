with open("ed_quant_engine/src/sentiment_filter.py", "r") as f:
    content = f.read()

new_logic = """
    async def fetch_sentiment(self, category: str):
        \"\"\"Asynchronously fetches news and calculates sentiment score with exponential backoff.\"\"\"
        url = self.feeds.get(category)
        if not url:
            return

        for attempt in range(3):
            try:
                # Running synchronous feedparser in a thread to prevent blocking
                feed = await asyncio.to_thread(feedparser.parse, url)

                # Fallback check
                if getattr(feed, "bozo", 0) == 1 and not feed.entries:
                    raise Exception("Feedparser error: Bad feed or connection issue.")

                compound_scores = []
                for entry in feed.entries[:10]: # Check last 10 news
                    score = self.sia.polarity_scores(entry.title)['compound']
                    compound_scores.append(score)

                if compound_scores:
                    avg_score = sum(compound_scores) / len(compound_scores)
                    self.cache[category] = avg_score
                    logger.info(f"Sentiment Updated for {category}: {avg_score:.2f}")

                break # Success, exit retry loop
            except Exception as e:
                sleep_time = 1 * (2 ** attempt)
                logger.warning(f"Failed to fetch sentiment for {category} (Attempt {attempt+1}): {e}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        else:
             logger.error(f"Failed to fetch sentiment for {category} after 3 attempts.")
"""

old_logic = """
    async def fetch_sentiment(self, category: str):
        \"\"\"Asynchronously fetches news and calculates sentiment score.\"\"\"
        url = self.feeds.get(category)
        if not url:
            return

        try:
            # Running synchronous feedparser in a thread to prevent blocking
            feed = await asyncio.to_thread(feedparser.parse, url)

            compound_scores = []
            for entry in feed.entries[:10]: # Check last 10 news
                score = self.sia.polarity_scores(entry.title)['compound']
                compound_scores.append(score)

            if compound_scores:
                avg_score = sum(compound_scores) / len(compound_scores)
                self.cache[category] = avg_score
                logger.info(f"Sentiment Updated for {category}: {avg_score:.2f}")
        except Exception as e:
            logger.warning(f"Failed to fetch sentiment for {category}: {e}")
"""

content = content.replace(old_logic.strip(), new_logic.strip())

with open("ed_quant_engine/src/sentiment_filter.py", "w") as f:
    f.write(content)
