import pandas as pd
import numpy as np
from typing import Dict, Any

from core.logger import logger
from core.database import fetch_dataframe

class PortfolioManager:
    """Aynı varlık gruplarındaki (Korelasyonlu) riski engeller ve Max Global Exposure (Açık Pozisyon) limitini yönetir."""

    def __init__(self, max_open_positions: int = 3, max_total_risk_pct: float = 0.06):
        self.max_open_positions = max_open_positions
        self.max_total_risk_pct = max_total_risk_pct # Toplam Kasanın %6'sı
        self.correlation_threshold = 0.75 # Pozitif Yüksek Korelasyon Sınırı

    def calculate_correlation_matrix(self, market_data: Dict[str, pd.DataFrame], lookback: int = 30) -> pd.DataFrame:
        """Son N günlük getiriler üzerinden Pearson Korelasyon Matrisi hesaplar."""
        close_prices = {}
        for ticker, (htf, ltf) in market_data.items():
            if not htf.empty and len(htf) >= lookback:
                # Sadece son 30 günün kapanış fiyatları
                close_prices[ticker] = htf['Close'].tail(lookback)

        if not close_prices:
            return pd.DataFrame()

        df_prices = pd.DataFrame(close_prices)
        df_returns = df_prices.pct_change().dropna()

        # Pearson
        return df_returns.corr()

    def correlation_veto(self, new_ticker: str, new_direction: str, open_positions_df: pd.DataFrame, corr_matrix: pd.DataFrame) -> bool:
        """
        Eğer yeni gelen sinyal, halihazırda açık olan pozisyonlarla yüksek oranda koreleyse ve
        aynı yöndeyse, riski katlamamak için VETO (Red) eder.
        """
        if open_positions_df.empty or corr_matrix.empty:
            return False

        if new_ticker not in corr_matrix.columns:
            return False # Verisi yoksa veto etme

        for _, pos in open_positions_df.iterrows():
            existing_ticker = pos['ticker']
            existing_direction = pos['direction']

            if existing_ticker in corr_matrix.columns:
                corr_value = corr_matrix.loc[new_ticker, existing_ticker]

                # Eğer iki varlık aynı yöne gidiyor (+0.75 korelasyon) ve sinyaller de aynı yöndeyse (Long/Long)
                if corr_value >= self.correlation_threshold and new_direction == existing_direction:
                    logger.warning(f"KORELASYON VETOSU: [{new_ticker}] ({new_direction}) sinyali reddedildi. [{existing_ticker}] ({existing_direction}) ile {corr_value:.2f} korelasyonlu.")
                    return True # Veto

                # Ters Korelasyon (-0.75) ve Zıt Yön (Biri Long, Diğeri Short) => Aslında aynı pozisyonu alıyorsun
                if corr_value <= -self.correlation_threshold and new_direction != existing_direction:
                    logger.warning(f"TERS KORELASYON VETOSU: [{new_ticker}] ({new_direction}) reddedildi. [{existing_ticker}] ({existing_direction}) ile zıt korele ({corr_value:.2f}). Riski katlıyor.")
                    return True # Veto

        return False

    def global_limit_veto(self, open_positions_df: pd.DataFrame, current_capital: float) -> bool:
        """Toplam aktif pozisyon sayısı veya toplam risk limitini kontrol eder."""
        if open_positions_df.empty:
            return False

        current_open_count = len(open_positions_df)
        if current_open_count >= self.max_open_positions:
            logger.warning(f"KAPASİTE DOLU VETOSU: Maksimum {self.max_open_positions} açık pozisyona ulaşıldı.")
            return True

        # Toplam Risk Edilen Miktar (Açık Pozisyonların Stop-Loss Mesafeleri Toplamı)
        total_risk_amount = 0.0
        for _, pos in open_positions_df.iterrows():
            entry = pos['entry_price']
            sl = pos['sl_price']
            size = pos['position_size']
            risk = abs(entry - sl) * size
            total_risk_amount += risk

        current_risk_pct = total_risk_amount / current_capital
        if current_risk_pct >= self.max_total_risk_pct:
            logger.warning(f"GLOBAL RİSK LİMİT VETOSU: Toplam risk kapasitesi aşıldı (%{current_risk_pct*100:.2f} > %{self.max_total_risk_pct*100:.2f}).")
            return True

        return False