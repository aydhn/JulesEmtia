import numpy as np
import pandas as pd
from config import MAX_GLOBAL_EXPOSURE, MAX_POSITIONS, CORRELATION_THRESHOLD
from core_engine import logger

class RiskManager:
    def __init__(self, db_ref):
        self.db = db_ref

    def check_correlation_veto(self, new_ticker: str, new_direction: str, universe_data_dict: dict) -> bool:
        # Phase 11: Dynamic Correlation Matrix
        open_trades = self.db.fetch_all("SELECT ticker, direction FROM trades WHERE status='Open'")
        if not open_trades: return False

        try:
            df_new = universe_data_dict.get(new_ticker)
            if df_new is None: return False

            for trade in open_trades:
                open_ticker, open_dir = trade[0], trade[1]
                df_open = universe_data_dict.get(open_ticker)
                if df_open is None: continue

                aligned = pd.merge(df_new['Close'].tail(30), df_open['Close'].tail(30), left_index=True, right_index=True)
                if len(aligned) > 10:
                    corr = aligned.corr().iloc[0, 1]
                    if corr > CORRELATION_THRESHOLD and new_direction == open_dir:
                        logger.info(f"Korelasyon Vetosu: {new_ticker} ile {open_ticker} çok benzeşiyor (Corr: {corr:.2f})")
                        return True
            return False
        except Exception as e:
            logger.error(f"Korelasyon Hesaplama Hatası: {e}")
            return False

    def calculate_kelly_position(self, capital: float, entry_price: float, sl_price: float) -> float:
        # Phase 15: Kelly Criterion & Position Sizing
        trades = self.db.fetch_all("SELECT pnl FROM trades WHERE status='Closed' ORDER BY trade_id DESC LIMIT 50")
        if not trades or len(trades) < 10:
            win_rate, profit_factor = 0.65, 1.5
        else:
            wins = [t[0] for t in trades if t[0] > 0]
            losses = [abs(t[0]) for t in trades if t[0] < 0]
            win_rate = len(wins) / len(trades)
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 1
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 1.5

        if profit_factor == 0 or win_rate == 0: return 0.0

        kelly_f = (profit_factor * win_rate - (1 - win_rate)) / profit_factor

        # JP Morgan Risk: Fractional Kelly & Safety Buffer
        fractional_kelly = max(0, kelly_f * 0.5)
        fractional_kelly = min(fractional_kelly, 0.04)

        open_count = len(self.db.fetch_all("SELECT trade_id FROM trades WHERE status='Open'"))
        if open_count >= MAX_POSITIONS:
            logger.info("Global Kapasite Limitine Ulaşıldı.")
            return 0.0

        risk_amount = capital * fractional_kelly
        stop_distance = abs(entry_price - sl_price)
        return risk_amount / stop_distance if stop_distance > 0 else 0

    def execution_simulator(self, asset_class: str, price: float, atr: float, direction: str) -> tuple:
        # Phase 21: Dynamic Spread & Slippage
        base_spreads = {"Metals": 0.0002, "Forex_TRY": 0.0010, "Energy": 0.0005, "Agriculture": 0.0008}
        spread = base_spreads.get(asset_class, 0.0005)

        slippage = (atr / price) * 0.15
        total_cost_percentage = (float(spread) / 2) + slippage
        cost_value = price * total_cost_percentage

        executed_price = price + cost_value if direction == "Long" else price - cost_value
        return executed_price, cost_value
