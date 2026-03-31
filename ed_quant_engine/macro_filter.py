import yfinance as yf
import pandas as pd
import asyncio
from logger import logger

class MacroRegimeFilter:
    """
    Market Regime Filter using macroeconomic indicators.
    Filters false positive technical signals during Risk-Off (Tightening) regimes.
    """

    TICKERS = {
        "DXY": "DX-Y.NYB",    # US Dollar Index (Liquidity/Risk Proxy)
        "US10Y": "^TNX",      # US 10-Year Treasury Yield (Interest Rate Pressure)
        "VIX": "^VIX"         # Volatility Index (Fear/Black Swan Monitor)
    }

    @classmethod
    async def fetch_macro_data(cls, period: str = "6mo") -> pd.DataFrame:
        """
        Asynchronously fetch macro data and build regime indicators.
        """
        try:
            # Download all macro tickers synchronously
            df = await asyncio.to_thread(yf.download, tickers=list(cls.TICKERS.values()), interval="1d", period=period, progress=False)

            if df.empty:
                logger.error("Failed to fetch macroeconomic data.")
                return pd.DataFrame()

            # Flatten multi-index
            if isinstance(df.columns, pd.MultiIndex):
                # We need Close prices for each ticker
                df = df['Close'].ffill().dropna()
            else:
                df = df.ffill().dropna()

            # Ensure TZ naive
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Calculate Regime Indicators (e.g. DXY 50 SMA)
            # Use Pandas rolling to compute indicators
            df['DXY_SMA50'] = df['DX-Y.NYB'].rolling(window=50).mean()
            df['US10Y_SMA50'] = df['^TNX'].rolling(window=50).mean()

            return df

        except Exception as e:
            logger.error(f"Error fetching macro data: {e}")
            return pd.DataFrame()

    @staticmethod
    def is_risk_off(macro_df: pd.DataFrame) -> bool:
        """
        Evaluates Risk-Off regime based on Macro Filters.
        Returns True if DXY and US10Y are in strong uptrends (Tightening Phase).
        """
        if macro_df.empty or len(macro_df) < 50:
            return False

        latest = macro_df.iloc[-1]
        prev = macro_df.iloc[-2]

        # Risk-Off criteria: Dollar is strengthening, Yields are rising.
        dxy_uptrend = latest['DX-Y.NYB'] > latest['DXY_SMA50']
        us10y_uptrend = latest['^TNX'] > latest['US10Y_SMA50']

        # Momentum check
        dxy_mom = latest['DX-Y.NYB'] > prev['DX-Y.NYB']
        us10y_mom = latest['^TNX'] > prev['^TNX']

        is_risk_off = (dxy_uptrend and us10y_uptrend) and (dxy_mom or us10y_mom)

        if is_risk_off:
            logger.info("Macro Filter: RISK-OFF Regime Detected. (Strong DXY & US10Y)")

        return is_risk_off

    @staticmethod
    def check_vix_circuit_breaker(macro_df: pd.DataFrame, threshold: float = 30.0) -> bool:
        """
        Black Swan & Flash Crash Protection (Phase 19).
        If VIX spikes above threshold or jumps violently, halt new entries.
        """
        if macro_df.empty or len(macro_df) < 2:
            return False

        latest_vix = macro_df.iloc[-1]['^VIX']
        prev_vix = macro_df.iloc[-2]['^VIX']

        vix_spike_pct = (latest_vix - prev_vix) / prev_vix * 100

        # Circuit Breaker triggers if VIX > 30 OR VIX spikes > 20% in one day
        if latest_vix > threshold or vix_spike_pct > 20.0:
            logger.critical(f"🚨 VIX CIRCUIT BREAKER TRIPPED! VIX at {latest_vix:.2f} (Spike: {vix_spike_pct:.2f}%). Halting new trades.")
            return True

        return False
