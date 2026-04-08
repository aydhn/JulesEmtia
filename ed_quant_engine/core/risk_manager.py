import yfinance as yf
import numpy as np
import pandas as pd
from typing import Tuple

from .infrastructure import PaperDB, logger
from .config import INITIAL_CAPITAL, MAX_RISK_PER_TRADE, GLOBAL_EXPOSURE_LIMIT, TICKERS, SPREADS, CORRELATION_THRESHOLD, VIX_THRESHOLD, Z_SCORE_THRESHOLD

class RiskManager:
    def __init__(self, db: PaperDB):
        self.db = db

    # ---------------- Phase 19: Black Swan & Micro Flash Crash ----------------
    def check_black_swan(self) -> bool:
        """Phase 19: VIX Devre Kesici ve Makro Şok Koruması."""
        try:
            vix = yf.download("^VIX", period="5d", progress=False)['Close'].iloc[-1]
            vix_val = float(vix.iloc[0]) if hasattr(vix, "iloc") else float(vix)
            if vix_val > VIX_THRESHOLD:
                logger.critical(f"SİYAH KUĞU ALARMI! VIX: {vix_val:.2f}. İşlemler donduruldu.")
                return True
        except Exception as e:
            logger.warning(f"Failed to check VIX: {e}")
        return False

    def check_z_score_anomaly(self, ticker: str, ltf_df: pd.DataFrame) -> bool:
        """Phase 19: Mikro Flaş Çöküş Tespit Edici (Z-Score Anomaly Detection)."""
        try:
            if ltf_df.empty or len(ltf_df) < 50:
                return False

            closes = ltf_df['Close']
            mean = closes.rolling(window=50).mean().iloc[-1]
            std = closes.rolling(window=50).std().iloc[-1]
            current = closes.iloc[-1]

            if std == 0:
                return False

            z_score = (current - mean) / std
            if abs(z_score) >= Z_SCORE_THRESHOLD:
                logger.critical(f"FLAŞ ÇÖKÜŞ ANOMALİSİ! {ticker} Z-Score: {z_score:.2f}")
                return True
        except Exception as e:
            logger.warning(f"Z-Score anomaly check failed for {ticker}: {e}")

        return False

    # ---------------- Phase 6: Macro Regime Filter ----------------
    def check_macro_veto(self, direction: str, category: str, macro_data: dict) -> bool:
        """Phase 6: Makroekonomik Filtreleme (DXY ve Tahvil Getirisi üzerinden)."""
        if category not in ["METALS", "FOREX", "AGRI"]:
            return False

        try:
            dxy_df = macro_data.get("DX-Y.NYB")
            tnx_df = macro_data.get("^TNX")

            if dxy_df is None or tnx_df is None or dxy_df.empty or tnx_df.empty:
                return False

            # Check if DXY is above its 50 SMA
            dxy_close = dxy_df['Close'].iloc[-1]
            dxy_sma50 = dxy_df['Close'].rolling(50).mean().iloc[-1]
            dxy_uptrend = dxy_close > dxy_sma50

            # Check if TNX is above its 50 SMA
            tnx_close = tnx_df['Close'].iloc[-1]
            tnx_sma50 = tnx_df['Close'].rolling(50).mean().iloc[-1]
            tnx_uptrend = tnx_close > tnx_sma50

            # If both are in an uptrend (Strong Dollar / High Yields = Risk Off for Metals/EM)
            if dxy_uptrend and tnx_uptrend and direction == "LONG":
                logger.warning(f"Macro Veto: DXY and Yields are rising. Rejecting {direction} for {category}.")
                return True

        except Exception as e:
            logger.warning(f"Macro veto check failed: {e}")

        return False

    # ---------------- Phase 11: Correlation & Portfolio Limits ----------------
    def check_portfolio_limits(self, new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame) -> bool:
        """Phase 11: Global Exposure & Correlation Veto."""
        open_pos = self.db.get_open_trades()

        if len(open_pos) >= GLOBAL_EXPOSURE_LIMIT:
            logger.warning(f"Global Exposure Limit ({GLOBAL_EXPOSURE_LIMIT}) reached. Vetoing {new_ticker}")
            return False

        if open_pos.empty:
            return True

        for _, trade in open_pos.iterrows():
            existing_ticker = trade['ticker']
            existing_dir = trade['direction']

            if existing_ticker == new_ticker and existing_dir == new_direction:
                return False

            if new_ticker in corr_matrix.columns and existing_ticker in corr_matrix.columns:
                corr = corr_matrix.loc[new_ticker, existing_ticker]
                if corr > CORRELATION_THRESHOLD and new_direction == existing_dir:
                    logger.warning(f"Correlation Veto: {new_ticker} vs {existing_ticker} (Corr: {corr:.2f})")
                    return False
        return True

    # ---------------- Phase 15: Kelly Sizing ----------------
    def calculate_kelly_fraction(self) -> float:
        """Phase 15: Geçmiş Performans Tabanlı Kelly Hesaplaması (Fractional)."""
        closed_trades = self.db.get_closed_trades()
        if len(closed_trades) < 10:
            return 0.01

        recent_trades = closed_trades.tail(50)
        wins = recent_trades[recent_trades['pnl'] > 0]
        losses = recent_trades[recent_trades['pnl'] <= 0]

        if len(wins) == 0:
            return 0.01

        p = len(wins) / len(recent_trades)
        q = 1.0 - p

        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 1.0

        if avg_loss == 0:
            return 0.01

        b = avg_win / avg_loss
        if b == 0:
            return 0.01

        f_star = (b * p - q) / b
        fractional_kelly = f_star / 2.0
        safe_kelly = max(0.005, min(fractional_kelly, MAX_RISK_PER_TRADE))
        logger.info(f"Dynamic Kelly Calculated: p={p:.2f}, b={b:.2f} -> Risk: {safe_kelly:.2%}")
        return safe_kelly

    def calculate_position_size(self, current_price: float, atr: float, balance: float) -> float:
        risk_pct = self.calculate_kelly_fraction()
        risk_amount = balance * risk_pct
        stop_distance = 1.5 * atr

        if stop_distance <= 0:
            return 0.0

        lot_size = risk_amount / stop_distance
        return round(lot_size, 4)

    # ---------------- Phase 21: Dynamic Slippage ----------------
    def dynamic_spread_slippage(self, ticker: str, current_price: float, atr: float) -> Tuple[float, float]:
        """Phase 21: Varlık Sınıfına Özgü Spread ve ATR Kaynaklı Kayma Maliyeti."""
        category = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")
        base_spread = SPREADS.get(category, 0.001)

        volatility_factor = (atr / current_price) / 0.005
        volatility_factor = max(1.0, min(volatility_factor, 3.0))

        slippage = (base_spread * 0.5) * volatility_factor
        return base_spread, slippage

    # ---------------- Phase 12: Trade Management ----------------
    def calculate_trailing_stop(self, direction: str, current_price: float, entry_price: float, current_sl: float, atr: float) -> float:
        """Phase 12: ATR Tabanlı Dinamik İzleyen Stop ve Başa Baş (Strictly Monotonic)."""
        new_sl = current_sl

        if direction == "LONG":
            if current_price >= entry_price + (1.0 * atr):
                if current_sl < entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")
            calculated_sl = current_price - (1.5 * atr)
            if calculated_sl > new_sl:
                new_sl = calculated_sl
        elif direction == "SHORT":
            if current_price <= entry_price - (1.0 * atr):
                if current_sl > entry_price:
                    new_sl = entry_price
                    logger.info("SL moved to Breakeven.")
            calculated_sl = current_price + (1.5 * atr)
            if calculated_sl < new_sl:
                new_sl = calculated_sl

        return new_sl

    def manage_positions(self, broker, current_prices: dict, current_atrs: dict, swan: bool):
        open_pos = self.db.get_open_trades()
        if open_pos.empty:
            return

        for _, row in open_pos.iterrows():
            tid, t, dir = row['trade_id'], row['ticker'], row['direction']
            e_p, sl, tp, size = row['entry_price'], row['sl_price'], row['tp_price'], row['position_size']

            if t not in current_prices:
                continue

            curr_p = current_prices[t]
            atr = current_atrs.get(t, curr_p * 0.01)
            pnl = (curr_p - e_p) * size if dir == 'LONG' else (e_p - curr_p) * size

            # SL / TP or Swan Trigger
            if (dir == 'LONG' and (curr_p <= sl or curr_p >= tp)) or (dir == 'SHORT' and (curr_p >= sl or curr_p <= tp)) or swan:
                broker.close_position(tid, curr_p, pnl)
                continue

            # Trailing Stop Update
            new_sl = self.calculate_trailing_stop(dir, curr_p, e_p, sl, atr)
            if new_sl != sl:
                broker.modify_trailing_stop(tid, new_sl)
