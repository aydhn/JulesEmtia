import pandas as pd
import numpy as np

from core.logger import logger

class QuantMath:
    """ED Capital Standartlarında Matematiksel Kasa Yönetimi (Fractional Kelly & Dinamik Kayma)."""

    def __init__(self, initial_capital: float = 10000.0, max_global_risk: float = 0.05):
        self.initial_capital = initial_capital
        self.max_global_risk = max_global_risk # Kasanın tek bir işlemde riske edilebilecek Tavan sınırı (Hard Cap)

        # Varlık Sınıflarına Göre Sabit Base Spread (Yüzdelik)
        self.base_spreads = {
            "Gold": 0.0002,
            "Silver": 0.0005,
            "Crude_Oil": 0.0003,
            "USDTRY": 0.0010, # Egzotik Kurlar daha yüksek makas
            "EURTRY": 0.0012
        }

    def calculate_kelly_fraction(self, past_trades_df: pd.DataFrame, min_trades: int = 10) -> float:
        """Geçmiş işlemlere bakarak kazanma oranını ve kâr/zarar oranını hesaplar (Kelly f*)."""
        if past_trades_df.empty or len(past_trades_df) < min_trades:
            return 0.02 # Yeterli veri yoksa sabit %2 risk

        wins = past_trades_df[past_trades_df['pnl'] > 0]
        losses = past_trades_df[past_trades_df['pnl'] <= 0]

        win_rate = len(wins) / len(past_trades_df)
        loss_rate = 1.0 - win_rate

        avg_win = wins['pnl'].mean() if not wins.empty else 0.0
        avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 1.0

        if avg_loss == 0.0:
            return 0.02

        # B değeri: Kâr/Zarar Oranı
        b = avg_win / avg_loss

        # Kelly Formülü: f* = (bp - q) / b
        f_star = ((b * win_rate) - loss_rate) / b

        # JP Morgan Risk Algısı: Kesirli (Half) Kelly
        fractional_kelly = f_star / 2.0

        # Kelly Negatifse (Strateji Çökmüşse) riski sıfırla/düşür
        if fractional_kelly <= 0:
            logger.warning(f"KELLY NEGATİF: Strateji avantajını kaybetti. (f*: {f_star:.2f})")
            return 0.005 # Min risk

        # Maksimum Hard Cap Koruması (Örn: %5'i asla geçme)
        return min(fractional_kelly, self.max_global_risk)

    def calculate_dynamic_execution_cost(self, ticker: str, current_price: float, current_atr: float, avg_atr: float) -> float:
        """Volatiliteye (ATR) duyarlı Dinamik Spread + Slippage (Fiyat Kayması) simülasyonu."""
        base_spread_pct = self.base_spreads.get(ticker, 0.0005) # Varsayılan %0.05

        # Volatilite Patlaması (ATR genişledikçe kayma artar)
        volatility_multiplier = 1.0
        if current_atr > avg_atr * 1.5:
            volatility_multiplier = 2.0 # %50 daha yüksek volatilite -> 2 kat kayma

        total_cost_pct = base_spread_pct * volatility_multiplier
        total_cost_abs = current_price * total_cost_pct

        return total_cost_abs

    def calculate_position_size(self, current_capital: float, risk_fraction: float, entry_price: float, sl_price: float) -> float:
        """Kelly veya Sabit risk oranıyla alınması gereken Lot (Position Size) miktarını belirler."""
        risk_amount = current_capital * risk_fraction
        sl_distance = abs(entry_price - sl_price)

        if sl_distance <= 0:
            return 0.0

        position_size = risk_amount / sl_distance
        return position_size