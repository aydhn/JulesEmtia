import pandas as pd
import numpy as np
from typing import Dict, Any, List
from .config import MAX_SINGLE_TRADE_CAP, ML_CONFIDENCE_THRESHOLD
from .execution_model import apply_execution_costs
from .ml_validator import check_ml_veto
from .sentiment_filter import check_sentiment_veto
from .paper_db import get_closed_trades
from .logger import log_info, log_error, log_warning

def calculate_kelly_position(current_balance: float, win_rate: float, avg_win_loss_ratio: float, atr_stop_dist: float) -> float:
    """
    Geçmiş Performansa Göre Fraksiyonel Kelly Kriteri (Yarım Kelly).
    Negatif çıkarsa işlem açılmaz.
    """
    # f* = (bp - q) / b (b=avg_win_loss_ratio, p=win_rate, q=1-win_rate)
    if avg_win_loss_ratio <= 0:
        return 0.0

    p = win_rate
    q = 1.0 - p
    b = avg_win_loss_ratio

    kelly_pct = (b * p - q) / b

    # Kötü Gidişat Koruması
    if kelly_pct <= 0:
        log_warning(f"📉 KELLY VETOSU: Kazanma oranı (%{p*100:.1f}) çok düşük. İşlem risk edilemez.")
        return 0.0

    # JP Morgan Risk Algısı (Yarım Kelly)
    fractional_kelly = kelly_pct / 2.0

    # Maksimum Tavan (Hard Cap) Koruması
    if fractional_kelly > MAX_SINGLE_TRADE_CAP:
        fractional_kelly = MAX_SINGLE_TRADE_CAP

    # Lot Miktarı (Risk Tutarı / Zarar Kes Mesafesi)
    risk_amount = current_balance * fractional_kelly
    if atr_stop_dist <= 0:
        return 0.0

    position_size = risk_amount / atr_stop_dist
    log_info(f"📊 KELLY ONAYI: %{fractional_kelly*100:.2f} Risk Ediliyor. Lot: {position_size:.4f}")
    return position_size

def analyze_signals(universe_mtf: Dict[str, Dict[str, pd.DataFrame]], current_balance: float, portfolio_manager: Any, open_trades: List[dict]) -> List[Dict]:
    """
    Çoklu Zaman Dilimli (MTF) ana Sinyal Üretim Mantığı.
    1. Günlük Trend Onayı (HTF)
    2. Saatlik Tetikleyici (LTF)
    3. ML Vetosu (Random Forest)
    4. Sentiment Vetosu (NLP)
    5. Korelasyon Vetosu (Portfolio Manager)
    6. Kelly ve Kayma Maliyetli (Slippage) Büyüklük Hesaplaması.
    """
    signals = []

    for ticker, data in universe_mtf.items():
        df_htf = data.get("1d")
        df_ltf = data.get("1h")

        if df_htf is None or df_ltf is None or len(df_ltf) < 2 or len(df_htf) < 2:
            continue

        # O Anki Aktif (Kapanmamış) mumu asla kullanma. Bir önceki (KAPANMIŞ) muma bak.
        # Bu, LOOKAHEAD BIAS'ı (Geleceği Görmeyi) %100 önler.
        last_closed_ltf = df_ltf.iloc[-2] # index -1 aktif mumdur.
        last_closed_htf = df_htf.iloc[-2] # index -1 bugündür (henüz kapanmadıysa tehlikelidir).

        # Güncel Piyasa Fiyatı (Sinyal bir önceki mumdan gelse de işlem anlık fiyattan girer)
        market_price = df_ltf['Close'].iloc[-1]

        # --- HTF (Günlük) Ana Trend Şartları ---
        htf_close = last_closed_htf['Close']
        htf_ema50 = last_closed_htf.get('EMA_50', 0)
        htf_macd = last_closed_htf.get('MACD_12_26_9', 0)

        htf_trend_up = (htf_close > htf_ema50) and (htf_macd > 0)
        htf_trend_down = (htf_close < htf_ema50) and (htf_macd < 0)

        # --- LTF (Saatlik) Kesin Giriş Şartları ---
        ltf_rsi = last_closed_ltf.get('RSI_14', 50)
        ltf_macd = last_closed_ltf.get('MACD_12_26_9', 0)
        ltf_bb_lower = last_closed_ltf.get('BBL_20_2.0', 0)
        ltf_bb_upper = last_closed_ltf.get('BBU_20_2.0', 0)
        ltf_close = last_closed_ltf['Close']

        direction = None

        # LONG Sinyali: Trend yukarı, Fiyat saatlikte ucuzlamış (Aşırı satım veya Alt Bant)
        if htf_trend_up and ((ltf_rsi < 35) or (ltf_close <= ltf_bb_lower)) and (ltf_macd > -0.5):
            direction = "Long"

        # SHORT Sinyali: Trend aşağı, Fiyat saatlikte şişmiş (Aşırı alım veya Üst Bant)
        elif htf_trend_down and ((ltf_rsi > 65) or (ltf_close >= ltf_bb_upper)) and (ltf_macd < 0.5):
            direction = "Short"

        if not direction:
            continue # Sinyal yok, sıradakine geç

        log_info(f"🔎 TEKNİK SİNYAL BULUNDU: [{ticker}] Yön: {direction} (Fiyat: {market_price:.4f})")

        # VETO 1: Machine Learning Doğrulaması (Random Forest)
        # Sinyal anındaki LTF verilerini Modele gönder
        if check_ml_veto(ticker, last_closed_ltf):
            continue

        # VETO 2: NLP Duyarlılık Filtresi (Haberler)
        if check_sentiment_veto(ticker, direction):
            continue

        # VETO 3: Korelasyon Matrisi (Risk Katlama Engeli)
        if portfolio_manager.check_correlation_veto(ticker, direction, open_trades):
            continue

        # ONAYLAR TAMAM! Maliyet ve Pozisyon Hesaplamalarına Geç

        # ATR Tabanlı Dinamik Stop Loss ve Take Profit
        atr = last_closed_ltf.get('ATRr_14', market_price * 0.01) # fallback %1
        avg_atr = df_ltf['ATRr_14'].rolling(50).mean().iloc[-2] # ATR'nin hareketli ortalaması (Kayma için)

        # Gerçekçi Maliyetler (Slippage + Spread)
        entry_price, slippage_abs, spread_abs = apply_execution_costs(ticker, direction, market_price, atr, avg_atr)

        # Hedefler Giriş Fiyatına Göre (Net Maliyetli Fiyat)
        if direction == "Long":
            sl_price = entry_price - (1.5 * atr)
            tp_price = entry_price + (3.0 * atr)
        else:
            sl_price = entry_price + (1.5 * atr)
            tp_price = entry_price - (3.0 * atr)

        atr_stop_dist = abs(entry_price - sl_price)


        # Kelly Büyüklük Hesaplaması (Daha önce SQLite'dan çekilmiş performans metriklerine göre)
        closed_trades = get_closed_trades()
        recent_trades = closed_trades[:50] if len(closed_trades) >= 10 else []

        if len(recent_trades) >= 10:
            wins = [t for t in recent_trades if t['pnl'] > 0]
            losses = [t for t in recent_trades if t['pnl'] <= 0]
            win_rate = len(wins) / len(recent_trades)
            avg_win = sum([t['pnl'] for t in wins]) / len(wins) if wins else 0
            avg_loss = abs(sum([t['pnl'] for t in losses]) / len(losses)) if losses else 1
            reward_risk = avg_win / avg_loss if avg_loss > 0 else 1.5
        else:
            win_rate = 0.60
            reward_risk = 1.5

        position_size = calculate_kelly_position(current_balance, win_rate, reward_risk, atr_stop_dist)
        # Kelly Koruması Vetosu
        if position_size <= 0:
            continue

        # VETO 4: Global Exposure Limit (Kasa Kapasitesi)
        risk_amount = position_size * atr_stop_dist
        if portfolio_manager.check_exposure_limit(current_balance, risk_amount, open_trades):
            continue

        # Tüm Filtrelerden Geçti, İletime Hazır (Execution)
        signals.append({
            "ticker": ticker,
            "direction": direction,
            "entry_price": entry_price, # Slippage ve Spread Dahil
            "sl_price": sl_price,
            "tp_price": tp_price,
            "position_size": position_size,
            "slippage": slippage_abs,
            "spread": spread_abs,
            "market_price": market_price,
            "atr": atr
        })

    return signals
