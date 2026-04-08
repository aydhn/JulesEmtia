with open("ed_quant_engine/src/data_engine.py", "r") as f:
    content = f.read()

new_logic = """
    async def fetch_mtf_data(self, ticker: str, period_1d="2y", period_1h="60d") -> tuple[pd.DataFrame, pd.DataFrame]:
        \"\"\"Fetches 1D and 1H data asynchronously with exponential backoff.\"\"\"
        for attempt in range(3):
            try:
                # yfinance operations are blocking, run in thread
                htf = await asyncio.to_thread(
                    yf.download, tickers=ticker, period=period_1d, interval="1d", progress=False
                )
                ltf = await asyncio.to_thread(
                    yf.download, tickers=ticker, period=period_1h, interval="1h", progress=False
                )

                # Basic cleaning (Phase 2)
                if not htf.empty: htf.ffill(inplace=True)
                if not ltf.empty: ltf.ffill(inplace=True)

                # Flatten MultiIndex columns if present (yfinance v0.2.x+ behavior)
                if isinstance(htf.columns, pd.MultiIndex):
                    htf.columns = [col[0] for col in htf.columns]
                if isinstance(ltf.columns, pd.MultiIndex):
                    ltf.columns = [col[0] for col in ltf.columns]

                # Drop missing values
                htf.dropna(inplace=True)
                ltf.dropna(inplace=True)

                return htf, ltf
            except Exception as e:
                sleep_time = 1 * (2 ** attempt)
                logger.warning(f"Error fetching data for {ticker} (Attempt {attempt+1}): {e}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)

        logger.error(f"Failed to fetch data for {ticker} after 3 attempts.")
        return pd.DataFrame(), pd.DataFrame()
"""

old_logic = """
    async def fetch_mtf_data(self, ticker: str, period_1d="2y", period_1h="60d") -> tuple[pd.DataFrame, pd.DataFrame]:
        \"\"\"Fetches 1D and 1H data asynchronously.\"\"\"
        try:
            # yfinance operations are blocking, run in thread
            htf = await asyncio.to_thread(
                yf.download, tickers=ticker, period=period_1d, interval="1d", progress=False
            )
            ltf = await asyncio.to_thread(
                yf.download, tickers=ticker, period=period_1h, interval="1h", progress=False
            )

            # Basic cleaning (Phase 2)
            if not htf.empty: htf.ffill(inplace=True)
            if not ltf.empty: ltf.ffill(inplace=True)

            # Flatten MultiIndex columns if present (yfinance v0.2.x+ behavior)
            if isinstance(htf.columns, pd.MultiIndex):
                htf.columns = [col[0] for col in htf.columns]
            if isinstance(ltf.columns, pd.MultiIndex):
                ltf.columns = [col[0] for col in ltf.columns]

            # Drop missing values
            htf.dropna(inplace=True)
            ltf.dropna(inplace=True)

            return htf, ltf
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame(), pd.DataFrame()
"""

content = content.replace(old_logic.strip(), new_logic.strip())

with open("ed_quant_engine/src/data_engine.py", "w") as f:
    f.write(content)
