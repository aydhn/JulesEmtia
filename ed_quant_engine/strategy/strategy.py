import pandas as pd
from config import Z_SCORE_ANOMALY
from core.logger import get_logger

logger = get_logger()

class StrategyEngine:
    def __init__(self, broker_interface):
        self.broker = broker_interface

    def generate_signal(self, df: pd.DataFrame) -> str:
        """MTF Confluence & Flash Crash Protection Signal Engine."""
        if df.empty or len(df) < 2: return "Hold"

        # Shift(1) to analyze ONLY closed candles (Zero Lookahead Bias)
        prev = df.iloc[-2]

        # Flash Crash Circuit Breaker (Z-Score Micro Anomaly)
        if abs(prev['Z_Score']) > Z_SCORE_ANOMALY:
            logger.critical(f"Mikro Flaş Çöküş: Z-Score {prev['Z_Score']:.2f} saptandı. İşlemler donduruldu.")
            return "Hold"

        # MTF CONFLUENCE LOGIC
        htf_trend_up = prev['HTF_Close'] > prev['HTF_EMA_50']
        htf_trend_dn = prev['HTF_Close'] < prev['HTF_EMA_50']

        # LONG SİNYALİ (Trend Up + RSI Oversold or Bounce off BB)
        if htf_trend_up:
            if prev['RSI'] < 30 or prev['Close'] <= prev['BBL_20_2']:
                if prev['MACD_Hist'] > 0: # Golden Cross Confirm
                    return "Long"

        # SHORT SİNYALİ (Trend Down + RSI Overbought or Reject off BB)
        elif htf_trend_dn:
            if prev['RSI'] > 70 or prev['Close'] >= prev['BBU_20_2']:
                if prev['MACD_Hist'] < 0: # Death Cross Confirm
                    return "Short"

        return "Hold"

    def manage_trailing_stops(self, open_positions: list, current_prices: dict, current_atrs: dict):
        """Trailing Stop & Breakeven Mechanism."""
        for trade in open_positions:
            t_id, ticker, direction, entry, sl, tp, size, status, _, _, _ = trade

            curr_price = current_prices.get(ticker)
            atr = current_atrs.get(ticker)
            if not curr_price or not atr: continue

            # CHECK FOR TP / SL HIT FIRST
            if direction == "Long":
                if curr_price >= tp or curr_price <= sl:
                    self.broker.close_order(t_id, curr_price)
                    continue
            else: # Short
                if curr_price <= tp or curr_price >= sl:
                    self.broker.close_order(t_id, curr_price)
                    continue

            # TRAILING STOP LOGIC
            new_sl = sl
            if direction == "Long":
                # Breakeven (Price moved +1 ATR in our favor)
                if curr_price > entry + atr and sl < entry:
                    new_sl = entry
                    logger.info(f"🔒 {ticker} Risk Sıfırlandı (Breakeven).")

                # Trailing (Strictly Monotonic)
                calc_sl = curr_price - (1.5 * atr)
                if calc_sl > new_sl:
                    new_sl = calc_sl

            elif direction == "Short":
                # Breakeven
                if curr_price < entry - atr and sl > entry:
                    new_sl = entry
                    logger.info(f"🔒 {ticker} Risk Sıfırlandı (Breakeven).")

                # Trailing (Strictly Monotonic)
                calc_sl = curr_price + (1.5 * atr)
                if calc_sl < new_sl:
                    new_sl = calc_sl

            # UPDATE DB IF SL CHANGED
            if new_sl != sl:
                self.broker.modify_stop_loss(t_id, new_sl)
