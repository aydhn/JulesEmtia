import pandas as pd
import yfinance as yf
from ed_quant_engine.utils.logger import setup_logger

logger = setup_logger("MacroFilter")

class MacroRegime:
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self.tnx_ticker = "^TNX"
        self.vix_ticker = "^VIX"

    def fetch_macro_data(self) -> pd.DataFrame:
        """Fetches macro indicators representing market regime."""
        try:
            tickers = [self.dxy_ticker, self.tnx_ticker, self.vix_ticker]
            df = yf.download(tickers, period="1y", interval="1d", progress=False)["Close"]
            df.ffill(inplace=True)
            return df
        except Exception as e:
            logger.error(f"Failed to fetch macro data: {e}")
            return pd.DataFrame()

    def get_regime(self, macro_df: pd.DataFrame) -> str:
        """Determines if the market is Risk-On, Risk-Off, or Neutral."""
        if macro_df.empty:
            return "Neutral"

        latest = macro_df.iloc[-1]

        # Black Swan / Circuit Breaker Check (Phase 19)
        if latest[self.vix_ticker] > 30.0:
            logger.critical(f"VIX Spike Detected: {latest[self.vix_ticker]}! BLACK SWAN REGIME.")
            return "Black_Swan"

        # Simplistic logic: Strong Dollar and High Yields = Risk-Off
        if latest[self.dxy_ticker] > macro_df[self.dxy_ticker].rolling(50).mean().iloc[-1] and \
           latest[self.tnx_ticker] > macro_df[self.tnx_ticker].rolling(50).mean().iloc[-1]:
             return "Risk_Off"

        return "Risk_On"

    @staticmethod
    def flash_crash_check(df: pd.DataFrame, window=50, threshold=4.0) -> bool:
        """Z-Score Anomaly Detection for single asset flash crashes."""
        if len(df) < window:
             return False

        close = df['Close']
        z_score = (close.iloc[-1] - close.rolling(window).mean().iloc[-1]) / close.rolling(window).std().iloc[-1]

        if abs(z_score) >= threshold:
             logger.warning(f"Flash Crash Anomaly! Z-Score: {z_score:.2f}")
             return True
        return False
