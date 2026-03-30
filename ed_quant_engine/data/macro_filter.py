import yfinance as yf
import pandas as pd
from core.logger import get_logger

logger = get_logger()

class MacroFilter:
    def __init__(self):
        self.dxy_ticker = "DX-Y.NYB"
        self.tnx_ticker = "^TNX"
        self.vix_ticker = "^VIX"

    def fetch_macro_data(self, ticker: str) -> pd.DataFrame:
        try:
            df = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if df.empty: return pd.DataFrame()
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.ffill(inplace=True)
            return df
        except Exception as e:
            logger.error(f"Macro Data Error ({ticker}): {e}")
            return pd.DataFrame()

    def get_macro_regime(self) -> dict:
        """Calculates current market regime and VIX Panic levels."""
        regime = {"Risk_Off": False, "Black_Swan": False, "VIX": 0.0}

        try:
            vix_df = self.fetch_macro_data(self.vix_ticker)
            dxy_df = self.fetch_macro_data(self.dxy_ticker)
            tnx_df = self.fetch_macro_data(self.tnx_ticker)

            if not vix_df.empty:
                current_vix = vix_df['Close'].iloc[-1]
                regime["VIX"] = current_vix

                # VIX Spike % Check (Flash Panic)
                vix_change = (current_vix - vix_df['Close'].iloc[-2]) / vix_df['Close'].iloc[-2]
                if vix_change > 0.15: # 15% jump in a single day
                    regime["Black_Swan"] = True
                    logger.critical(f"SİYAH KUĞU UYARISI: VIX aniden %{vix_change*100:.1f} zıpladı.")

            if not dxy_df.empty and not tnx_df.empty:
                # 5-day SMA to avoid daily noise
                dxy_sma = dxy_df['Close'].rolling(5).mean().iloc[-1]
                tnx_sma = tnx_df['Close'].rolling(5).mean().iloc[-1]

                # If Dollar AND Yields are rising, it's Risk-Off (Bad for Gold/EM Currencies)
                if dxy_df['Close'].iloc[-1] > dxy_sma and tnx_df['Close'].iloc[-1] > tnx_sma:
                    regime["Risk_Off"] = True

        except Exception as e:
            logger.error(f"Error computing macro regime: {e}")

        return regime
