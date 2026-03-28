import pandas as pd
from core.config import FRACTIONAL_KELLY, MAX_TOTAL_RISK_PCT, CORRELATION_THRESHOLD
from core.logger import logger

class PortfolioManager:
    def __init__(self, db):
        self.db = db

    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if win_rate == 0 or avg_loss == 0:
            return 0.0

        b = avg_win / abs(avg_loss)
        q = 1.0 - win_rate

        # Kelly formula: f* = (bp - q) / b
        full_kelly = (b * win_rate - q) / b

        if full_kelly <= 0:
            logger.warning(f"Kelly Kriteri negatif veya sıfır: {full_kelly:.4f}. Minimum risk uygulanacak.")
            return 0.0

        fractional_risk = full_kelly * FRACTIONAL_KELLY
        final_risk = min(fractional_risk, MAX_TOTAL_RISK_PCT)

        logger.info(f"Dinamik Kelly Riski (WinRate: {win_rate:.2f}, K/Z: {b:.2f}) -> Hedef Risk: %{final_risk*100:.2f}")
        return final_risk

    def correlation_veto(self, new_ticker: str, direction: str, universe_df: pd.DataFrame) -> bool:
        """
        universe_df should be a DataFrame with 'Close' prices of multiple tickers to calculate a matrix.
        If universe_df just contains OHLCV for new_ticker, this logic is skipped.
        Ideally we need a global universe pricing matrix.
        """
        open_trades = self.db.get_open_trades()
        if open_trades.empty: return False

        try:
            # Requires multi-ticker dataframe like yfinance returns when passing a list
            if isinstance(universe_df.columns, pd.MultiIndex):
                 # Close prices for all tickers
                 close_df = universe_df['Close']
                 corr_matrix = close_df.corr()

                 for _, trade in open_trades.iterrows():
                     if trade['direction'] == direction:
                         if new_ticker in corr_matrix.index and trade['ticker'] in corr_matrix.columns:
                             corr = corr_matrix.loc[new_ticker, trade['ticker']]
                             if corr > CORRELATION_THRESHOLD:
                                 logger.info(f"Korelasyon Riski: {new_ticker} ile {trade['ticker']} korelasyonu {corr:.2f}")
                                 return True
        except Exception as e:
            logger.error(f"Korelasyon hesaplama hatası: {e}")

        return False
