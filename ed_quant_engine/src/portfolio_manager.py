import pandas as pd
import numpy as np
from typing import Dict, List
from .config import MAX_OPEN_POSITIONS, MAX_GLOBAL_RISK_PCT, CORRELATION_THRESHOLD
from .logger import log_info, log_error, log_warning

class PortfolioManager:
    """
    ED Capital Risk Yönetimi:
    1. Tüm açık işlemlerin maksimum riskini (Global Exposure) denetler.
    2. Dinamik korelasyon hesaplayarak aynı anda aynı yönlü yüksek korelasyonlu işlemleri reddeder.
    """

    def __init__(self):
        self.correlation_matrix = pd.DataFrame()
        self.max_positions = MAX_OPEN_POSITIONS
        self.max_risk_pct = MAX_GLOBAL_RISK_PCT
        self.corr_threshold = CORRELATION_THRESHOLD

    def update_correlation_matrix(self, universe_data: Dict[str, pd.DataFrame]):
        """
        Geçmiş 60 günlük kapanış verileri üzerinden yuvarlanan (rolling)
        Pearson Korelasyon Matrisi oluşturur. (CPU/RAM dostu Pandas işlemi)
        """
        log_info("Dinamik Korelasyon Matrisi Güncelleniyor...")
        try:
            close_prices = {}
            for ticker, data in universe_data.items():
                df = data.get("1d")
                if df is not None and not df.empty and "Close" in df.columns:

                    # Sadece son 60 günlük kapanış fiyatları
                    close_prices[ticker] = df['Close'].tail(60)

            df_closes = pd.DataFrame(close_prices)

            # Günlük % Değişimler üzerinden korelasyon (Fiyatlar yanıltıcıdır)
            returns = df_closes.pct_change().dropna()
            self.correlation_matrix = returns.corr(method='pearson')
            log_info(f"Matris {len(returns)} varlık için güncellendi.")

        except Exception as e:
            log_error(f"Korelasyon Matrisi Hatası: {e}")

    def check_correlation_veto(self, new_ticker: str, new_direction: str, open_trades: List[dict]) -> bool:
        """
        Eğer yeni sinyal gelen varlık, halihazırda AÇIK olan bir varlık ile
        belirlenen eşik üzerinde (>0.75) pozitif korelasyonluysa ve yönleri aynıysa (Long-Long)
        veya yüksek negatif korelasyonlu ve yönleri zıtsa (Long-Short) VETO atar.
        """
        if self.correlation_matrix.empty or new_ticker not in self.correlation_matrix.columns:
            return False

        for trade in open_trades:
            open_ticker = trade['ticker']
            open_direction = trade['direction']

            if open_ticker not in self.correlation_matrix.columns:
                continue

            corr_value = self.correlation_matrix.loc[new_ticker, open_ticker]

            # Risk Duplication: Altın Long varken Gümüş Long geldiğinde (Korelasyon > 0.75)
            if corr_value > self.corr_threshold and new_direction == open_direction:
                log_warning(f"🚨 KORELASYON VETOSU: {new_ticker} ({new_direction}) sinyali, {open_ticker} ({open_direction}) ile çok benzer hareket ediyor (Korelasyon: {corr_value:.2f}).")
                return True

            # Ters Korelasyonlu Varlıkta Zıt İşlem: USDTRY Long varken EURUSD Short geldiğinde (-0.80 ise)
            if corr_value < -self.corr_threshold and new_direction != open_direction:
                log_warning(f"🚨 KORELASYON VETOSU: {new_ticker} ({new_direction}) sinyali, {open_ticker} ({open_direction}) ile ters korelasyonlu ({corr_value:.2f}). Risk katlanıyor!")
                return True

        return False

    def check_exposure_limit(self, current_balance: float, new_risk_amount: float, open_trades: List[dict]) -> bool:
        """
        Açık işlemlerin toplam riskinin, Kasanın Maksimum Yüzdesini (Örn %6)
        geçip geçmediğini ve pozisyon sayısı sınırını denetler.
        """
        if len(open_trades) >= self.max_positions:
            log_warning(f"🚨 KAPASİTE DOLU VETOSU: Maksimum açık pozisyon sınırına ({self.max_positions}) ulaşıldı.")
            return True

        total_current_risk = sum(
            abs(t['entry_price'] - t['sl_price']) * t['position_size']
            for t in open_trades
        )

        projected_total_risk = total_current_risk + new_risk_amount
        max_allowed_risk = current_balance * self.max_risk_pct

        if projected_total_risk > max_allowed_risk:
            log_warning(f"🚨 GLOBAL RİSK VETOSU: Yeni işlemle risk ({projected_total_risk:.2f}$) limiti ({max_allowed_risk:.2f}$) aşıyor.")
            return True

        return False
