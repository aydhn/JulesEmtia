import yfinance as yf
import pandas as pd
from src.logger import logger
import asyncio

class MacroFilter:
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self.tnx_ticker = "^TNX"
        self.benchmark_ticker = "USDTRY=X"

    async def fetch_macro_data(self) -> pd.DataFrame:
        try:
            dxy_df = await asyncio.to_thread(yf.download, tickers=self.dxy_ticker, period="1mo", interval="1d", progress=False)
            tnx_df = await asyncio.to_thread(yf.download, tickers=self.tnx_ticker, period="1mo", interval="1d", progress=False)

            macro_df = pd.DataFrame(index=dxy_df.index)
            macro_df['DXY'] = dxy_df['Close']
            macro_df['TNX'] = tnx_df['Close']

            macro_df = macro_df.ffill().dropna()

            # Simple Trend Logic: Price > 50 SMA (approximated on shorter timeframe if needed)
            # For robustness, just check short term momentum if not enough data
            macro_df['DXY_SMA_5'] = macro_df['DXY'].rolling(window=5).mean()
            macro_df['TNX_SMA_5'] = macro_df['TNX'].rolling(window=5).mean()

            return macro_df
        except Exception as e:
            logger.error(f"Error fetching macro data: {e}")
            return pd.DataFrame()

    async def get_market_regime(self) -> str:
        macro_df = await self.fetch_macro_data()
        if macro_df.empty or len(macro_df) < 5:
            return "Neutral"

        last_row = macro_df.iloc[-1]

        dxy_uptrend = last_row['DXY'] > last_row['DXY_SMA_5']
        tnx_uptrend = last_row['TNX'] > last_row['TNX_SMA_5']

        if dxy_uptrend and tnx_uptrend:
            return "Risk-Off" # Strong USD & Yields = Bad for risk assets/commodities
        elif not dxy_uptrend and not tnx_uptrend:
            return "Risk-On"  # Weak USD & Yields = Good for risk assets/commodities
        else:
            return "Neutral"

    def veto_signal(self, ticker: str, direction: str, regime: str) -> bool:
        """
        Returns True if the signal should be vetoed based on macro regime.
        """
        # Ex: If Risk-Off (Strong USD), veto Longs on Gold/Silver/Emerging FX
        if regime == "Risk-Off" and direction == "Long":
            logger.info(f"Macro Veto: Rejected {direction} on {ticker} due to Risk-Off regime (DXY & TNX rising).")
            return True

        # Ex: If Risk-On (Weak USD), veto Shorts on Risk Assets (or USDTRY Longs if applicable, though TRY dynamics are complex)
        # Simplified for now.
        return False

    async def get_benchmark_return(self, start_date: str) -> float:
        try:
            df = await asyncio.to_thread(yf.download, tickers=self.benchmark_ticker, start=start_date, progress=False)
            if df.empty: return 0.0

            first_price = df['Close'].iloc[0]
            last_price = df['Close'].iloc[-1]
            pct_change = ((last_price - first_price) / first_price) * 100
            return pct_change
        except Exception as e:
            logger.error(f"Error fetching benchmark: {e}")
            return 0.0
