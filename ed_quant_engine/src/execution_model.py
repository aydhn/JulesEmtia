import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple
from .config import SPREADS
from .logger import log_info, log_error, log_warning

def calculate_dynamic_slippage(ticker: str, atr: float, avg_atr: float, base_spread: float) -> float:
    """
    Volatiliteye (ATR) bağlı dinamik kayma maliyeti (Slippage) hesaplar.
    O anki ATR, ortalamadan ne kadar yüksekse kayma o kadar artar.
    """
    if np.isnan(atr) or np.isnan(avg_atr) or avg_atr == 0:
        return base_spread / 2

    volatility_ratio = atr / avg_atr

    # Eğer volatilite normalse (oran 1 civarıysa), standart kayma uygula
    if volatility_ratio <= 1.2:
        slippage = base_spread / 2
    else:
        # Volatilite patladıysa (Örn 1.5 katıysa), kaymayı (1.5)^2 oranında artır
        slippage = (base_spread / 2) * (volatility_ratio ** 2)
        log_warning(f"🚨 YÜKSEK VOLATİLİTE KAYMASI: [{ticker}] ATR Oranı: {volatility_ratio:.2f}, Kayma Maliyeti: {slippage:.5f}")

    return slippage

def get_base_spread(ticker: str) -> float:
    """
    Varlığın kategorisine göre sabit baz spread (Alış-Satış Makası) yüzdesini döndürür.
    """
    if "TRY" in ticker:
        return SPREADS["Forex_TRY"]
    elif ticker in ["GC=F", "SI=F", "HG=F", "PA=F", "PL=F"]:
        return SPREADS["Metals"]
    elif ticker in ["CL=F", "BZ=F", "NG=F", "HO=F", "RB=F"]:
        return SPREADS["Energy"]
    else:
        return SPREADS["Agriculture"]

def apply_execution_costs(ticker: str, direction: str, market_price: float, atr: float, avg_atr: float) -> Tuple[float, float, float]:
    """
    Sinyal geldiğinde (Giriş) ve işlem kapanırken (Çıkış) kusursuz fiyattan işlemi gerçekleştirmez.
    Makas (Spread) ve Kayma (Slippage) maliyetlerini ekleyerek GERÇEK (Net of Fees) fiyatı hesaplar.
    """
    base_spread_pct = get_base_spread(ticker)
    base_spread_abs = market_price * base_spread_pct

    dynamic_slippage_abs = market_price * calculate_dynamic_slippage(ticker, atr, avg_atr, base_spread_pct)

    # Giriş Maliyeti
    if direction == "Long":
        entry_price = market_price + (base_spread_abs / 2) + dynamic_slippage_abs
        # Çıkış maliyeti önizlemesi (Spread kadar daha zarar yazacak)
        exit_price_preview = market_price - (base_spread_abs / 2) - dynamic_slippage_abs
    else:
        entry_price = market_price - (base_spread_abs / 2) - dynamic_slippage_abs
        exit_price_preview = market_price + (base_spread_abs / 2) + dynamic_slippage_abs

    total_cost_pct = abs((entry_price - market_price) / market_price) + abs((exit_price_preview - market_price) / market_price)
    log_info(f"[{ticker}] Gerçekçi İletim Maliyeti (Slippage+Spread): %{total_cost_pct*100:.4f}")

    return entry_price, dynamic_slippage_abs, base_spread_abs
