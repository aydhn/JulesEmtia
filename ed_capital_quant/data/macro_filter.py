import pandas as pd
from data.data_loader import DataLoader
from scipy.stats import zscore
from core.logger import logger
import numpy as np

class MacroRegime:
    @staticmethod
    def check_black_swan() -> bool:
        vix_df = DataLoader.fetch_data("^VIX", "1d", "1mo")
        if vix_df.empty: return False

        try:
            # Handle MultiIndex if present
            close_prices = vix_df['Close']
            if isinstance(vix_df.columns, pd.MultiIndex):
                close_prices = vix_df['Close'].iloc[:, 0]

            last_vix = close_prices.iloc[-1].item()
            prev_vix = close_prices.iloc[-2].item()
            vix_jump = (last_vix - prev_vix) / prev_vix

            if last_vix > 35 or vix_jump > 0.20:
                logger.critical(f"🚨 SİYAH KUĞU TESPİTİ! VIX: {last_vix:.2f}. Devre Kesiciler Aktif.")
                return True
        except Exception as e:
            logger.error(f"Black swan check error: {e}")

        return False

    @staticmethod
    def is_flash_crash(df: pd.DataFrame) -> bool:
        if len(df) < 50: return False
        try:
            # Flatten multi-index if necessary
            close_prices = df['Close'] if not isinstance(df.columns, pd.MultiIndex) else df['Close'].iloc[:, 0]
            z_scores = zscore(close_prices.dropna())
            last_z = z_scores.iloc[-1]
            if abs(last_z) > 4.5:
                logger.warning(f"Flaş Çöküş Anomalisi! Z-Score: {last_z:.2f}")
                return True
        except Exception as e:
            logger.error(f"Flash crash detection error: {e}")
        return False

    @staticmethod
    def veto_signal(signal: str, ticker: str) -> bool:
        """
        DXY and US 10Y Yields check for market regime
        Returns True to veto (reject) the signal, False to allow it.
        """
        try:
            dxy_df = DataLoader.fetch_data("DX-Y.NYB", "1d", "6mo")
            tnx_df = DataLoader.fetch_data("^TNX", "1d", "6mo")

            if dxy_df.empty or tnx_df.empty:
                return False

            dxy_close = dxy_df['Close'] if not isinstance(dxy_df.columns, pd.MultiIndex) else dxy_df['Close'].iloc[:, 0]
            tnx_close = tnx_df['Close'] if not isinstance(tnx_df.columns, pd.MultiIndex) else tnx_df['Close'].iloc[:, 0]

            # Calculate 50 SMA for DXY and TNX to determine trend
            dxy_sma_50 = dxy_close.rolling(window=50).mean().iloc[-1]
            tnx_sma_50 = tnx_close.rolling(window=50).mean().iloc[-1]

            dxy_last = dxy_close.iloc[-1]
            tnx_last = tnx_close.iloc[-1]

            risk_off = (dxy_last > dxy_sma_50) and (tnx_last > tnx_sma_50)

            # Risk-Off Regime (Tightening, Strong Dollar)
            if risk_off:
                # Reject Longs on Metals and Emerging Markets (TRY pairs)
                if signal == "Long" and (ticker in ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"] or "TRY" in ticker):
                    logger.info(f"Makro Veto: Risk-Off Rejimi. {ticker} Long sinyali reddedildi.")
                    return True

        except Exception as e:
            logger.error(f"Makro filtre hatası: {e}")

        return False
