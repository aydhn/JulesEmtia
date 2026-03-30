import yfinance as yf
import numpy as np
import pandas as pd
from core.data_engine import db
from core.config import INITIAL_CAPITAL, MAX_RISK_PER_TRADE, GLOBAL_EXPOSURE_LIMIT
from system.logger import log

class RiskManager:
    @staticmethod
    def check_black_swan() -> bool:
        """Phase 19: VIX Devre Kesici ve Makro Şok Koruması"""
        try:
            vix = yf.download("^VIX", period="5d", progress=False)['Close'].iloc[-1]
            if vix > 35.0:
                log.critical(f"SİYAH KUĞU ALARMI! VIX: {vix:.2f}. İşlemler donduruldu.")
                return True
        except Exception as e:
            log.warning(f"Failed to check VIX: {e}")
        return False

    @staticmethod
    def check_z_score_anomaly(ticker: str, ltf_df: pd.DataFrame) -> bool:
        """Phase 19: Mikro Flaş Çöküş Tespit Edici (Z-Score Anomaly Detection)"""
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
            if abs(z_score) >= 4.0:
                log.critical(f"FLAŞ ÇÖKÜŞ ANOMALİSİ! {ticker} Z-Score: {z_score:.2f}")
                return True
        except Exception as e:
            log.warning(f"Z-Score anomaly check failed for {ticker}: {e}")

        return False

    @staticmethod
    def check_correlation_veto(new_ticker: str, ltf_dict: dict) -> bool:
        """Phase 11: Risk Duplication Filtresi"""
        open_pos = db.get_open_positions()
        if len(open_pos) >= GLOBAL_EXPOSURE_LIMIT:
            log.warning(f"Global Exposure Limit ({GLOBAL_EXPOSURE_LIMIT}) reached. Vetoing {new_ticker}")
            return True

        if open_pos.empty:
            return False

        df = pd.DataFrame()
        for t in open_pos['ticker'].tolist() + [new_ticker]:
            if t in ltf_dict and 'Close' in ltf_dict[t].columns:
                df[t] = ltf_dict[t]['Close']

        if not df.empty and new_ticker in df.columns:
            corr_matrix = df.corr()
            for open_t in open_pos['ticker']:
                if open_t in corr_matrix.columns and abs(corr_matrix.loc[new_ticker, open_t]) > 0.75:
                    log.warning(f"Korelasyon Vetosu: {new_ticker} ile {open_t} yüksek korele.")
                    return True
        return False

    @staticmethod
    def calculate_fractional_kelly() -> float:
        """Phase 15: Kelly Kriteri ile Dinamik Kasa Büyütme (Yarım Kelly)"""
        try:
            trades = pd.read_sql_query("SELECT pnl FROM trades WHERE status='CLOSED' ORDER BY trade_id DESC LIMIT 50", db.conn)
            if len(trades) < 10:
                return 0.01

            wins, losses = trades[trades['pnl'] > 0], trades[trades['pnl'] <= 0]
            win_rate = len(wins) / len(trades)

            avg_win = wins['pnl'].mean() if len(wins) > 0 else 1
            avg_loss = abs(losses['pnl'].mean()) if len(losses) > 0 else 1

            if avg_loss == 0:
                return 0.01

            b = avg_win / avg_loss
            kelly = (b * win_rate - (1 - win_rate)) / b
            return max(0.005, min(kelly / 2.0, MAX_RISK_PER_TRADE)) # Güvenlik: Half-Kelly ve Hard Cap
        except Exception as e:
            log.error(f"Error calculating Kelly: {e}")
            return 0.01

    @staticmethod
    def manage_positions(broker, current_prices: dict, current_atrs: dict, swan: bool):
        """Phase 12: İzleyen Stop (Strictly Monotonic) ve Başa Baş (Breakeven)"""
        open_pos = db.get_open_positions()
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

            # SL / TP Kontrolü
            if (dir == 'LONG' and (curr_p <= sl or curr_p >= tp)) or (dir == 'SHORT' and (curr_p >= sl or curr_p <= tp)) or swan:
                broker.close_position(tid, curr_p, pnl)
                continue

            # İzleyen Stop
            new_sl = sl
            if dir == 'LONG':
                if curr_p > e_p + atr:
                    new_sl = max(sl, e_p) # Breakeven
                new_sl = max(new_sl, curr_p - (1.5 * atr)) # Trailing
            else:
                if curr_p < e_p - atr:
                    new_sl = min(sl, e_p) # Breakeven
                new_sl = min(new_sl, curr_p + (1.5 * atr)) # Trailing

            if new_sl != sl:
                db.update_sl(tid, new_sl)
                log.info(f"🔒 {t} SL Revizesi: {new_sl:.4f}")
