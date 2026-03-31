import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import datetime
from typing import Dict, Any, List, Tuple
from logger import get_logger
import paper_db

logger = get_logger("quant_logic")

MODEL_PATH = "models/rf_model.pkl"

class MLValidator:
    """Random Forest Classifier for Signal Validation (Win Probability)."""

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
        self.is_trained = False
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_trained = True
                logger.info("Loaded pre-trained ML Model.")
            except Exception as e:
                logger.error(f"Failed loading ML Model: {e}")

    def create_labels(self, df: pd.DataFrame, target_return: float = 0.02, look_forward: int = 24) -> pd.DataFrame:
        """
        Creates target labels (1 for success, 0 for failure) by looking forward
        N periods to see if a hypothetical 2% profit was reached before a 1% loss.
        """
        if len(df) < look_forward + 1:
            return df

        # Shift future returns backward to the current row
        future_highs = df['High'].rolling(window=look_forward).max().shift(-look_forward)
        future_lows = df['Low'].rolling(window=look_forward).min().shift(-look_forward)
        current_close = df['Close']

        # 1 if price went up by target_return before it went down by half of target_return
        success_long = (future_highs >= current_close * (1 + target_return)) & (future_lows > current_close * (1 - (target_return/2)))
        success_short = (future_lows <= current_close * (1 - target_return)) & (future_highs < current_close * (1 + (target_return/2)))

        df['TARGET_LONG'] = success_long.astype(int)
        df['TARGET_SHORT'] = success_short.astype(int)

        return df.dropna()

    def train_model(self, combined_df: pd.DataFrame):
        """Trains the Random Forest model on historical feature set."""
        if combined_df.empty:
            return

        # Select Features (Excluding future targets, timestamps, string columns)
        features = combined_df.select_dtypes(include=[np.number]).drop(columns=['TARGET_LONG', 'TARGET_SHORT'], errors='ignore')

        # For simplicity, we train one model for "Is it a good time to enter ANY trade?"
        # A more advanced setup would have separate models for Long/Short.
        y = combined_df['TARGET_LONG'] | combined_df['TARGET_SHORT']

        try:
            self.model.fit(features, y)
            joblib.dump(self.model, MODEL_PATH)
            self.is_trained = True
            logger.info(f"ML Model retrained successfully on {len(features)} samples.")
        except Exception as e:
            logger.error(f"ML Training Failed: {e}")

    def predict_probability(self, features_row: pd.Series) -> float:
        """Predicts the probability of success for a new signal."""
        if not self.is_trained:
            return 0.5 # Neutral if not trained

        try:
            # Reshape for sklearn
            X = features_row.to_frame().T
            proba = self.model.predict_proba(X)[0][1] # Probability of Class 1 (Success)
            return proba
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return 0.5


class PortfolioManager:
    """Handles Position Sizing (Fractional Kelly) and Correlation Risk."""

    def __init__(self, max_open_trades: int = 3, max_portfolio_risk: float = 0.06):
        self.max_open_trades = max_open_trades
        self.max_portfolio_risk = max_portfolio_risk
        self.correlation_matrix = pd.DataFrame()

    def update_correlation_matrix(self, close_prices_df: pd.DataFrame):
        """Calculates rolling 30-day Pearson correlation matrix."""
        if not close_prices_df.empty:
            self.correlation_matrix = close_prices_df.corr(method='pearson')
            logger.info("Correlation matrix updated.")

    def is_vetoed_by_correlation(self, new_ticker: str, new_direction: str, threshold: float = 0.75) -> bool:
        """Vetoes a signal if we already hold a highly correlated asset in the same direction."""
        open_trades = paper_db.get_open_trades()

        if not open_trades or self.correlation_matrix.empty or new_ticker not in self.correlation_matrix.columns:
            return False

        for trade in open_trades:
            existing_ticker = trade['ticker']
            existing_dir = trade['direction']

            if existing_ticker in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[new_ticker, existing_ticker]

                # High positive correlation AND same direction = Risk Duplication
                if corr >= threshold and new_direction == existing_dir:
                    logger.warning(f"CORRELATION VETO: {new_ticker} {new_direction} rejected due to {corr:.2f} correlation with open {existing_ticker}.")
                    return True

                # High negative correlation AND opposite direction = Risk Duplication
                if corr <= -threshold and new_direction != existing_dir:
                    logger.warning(f"CORRELATION VETO: {new_ticker} {new_direction} rejected due to {corr:.2f} inverse correlation with open {existing_ticker}.")
                    return True

        return False

    def calculate_fractional_kelly(self, win_rate: float, win_loss_ratio: float) -> float:
        """
        Calculates Half-Kelly fraction.
        Formula: f* = (bp - q) / b
        Where b is the odds (Win/Loss Ratio), p is win prob, q is loss prob.
        """
        if win_loss_ratio <= 0 or win_rate <= 0:
            return 0.0

        p = win_rate
        q = 1.0 - p
        b = win_loss_ratio

        kelly_f = (b * p - q) / b

        # JP Morgan Risk Algısı: Half-Kelly
        fractional_kelly = kelly_f / 2.0

        # Hard Caps: Never risk more than 4% on a single trade, or less than 0.5% if valid
        if fractional_kelly > 0:
            return min(max(fractional_kelly, 0.005), 0.04)
        return 0.0

    def get_position_size(self, current_balance: float, entry_price: float, sl_price: float) -> float:
        """Calculates position size based on historical Kelly Criterion."""
        closed_trades = paper_db.get_closed_trades(limit=50)

        if len(closed_trades) < 10:
            # Not enough data, use fixed 2% risk
            risk_amount = current_balance * 0.02
        else:
            wins = [t for t in closed_trades if t['pnl'] > 0]
            losses = [t for t in closed_trades if t['pnl'] <= 0]

            win_rate = len(wins) / len(closed_trades) if closed_trades else 0

            avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
            avg_loss = abs(sum(t['pnl'] for t in losses) / len(losses)) if losses else 1.0 # Prevent div by 0

            win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

            kelly_pct = self.calculate_fractional_kelly(win_rate, win_loss_ratio)
            risk_amount = current_balance * kelly_pct

            logger.info(f"Kelly Stats: WR={win_rate:.2f}, W/L={win_loss_ratio:.2f} -> Risking {kelly_pct*100:.2f}%")

            if kelly_pct <= 0:
                logger.warning("Negative Kelly: Strategy edge lost. Skipping trade.")
                return 0.0

        # Calculate Lot Size
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            return 0.0

        qty = risk_amount / sl_distance
        return round(qty, 4)


class StrategyEngine:
    """Core Strategy Logic with MTF Confluence."""

    def __init__(self):
        self.ml_validator = MLValidator()
        self.portfolio_mgr = PortfolioManager()

    def generate_signal(self, df: pd.DataFrame, ticker: str) -> Dict[str, Any]:
        """
        Analyzes the LAST CLOSED CANDLE (shift(1) equivalent) for signals.
        Returns a signal dictionary if conditions are met.
        """
        if df.empty or len(df) < 2:
            return None

        # We only look at the row before the last one (closed candle)
        # to strictly prevent lookahead bias in live trading.
        current_idx = -2

        try:
            row = df.iloc[current_idx]

            # 1. MTF Trend Filter (Daily) - MASTER VETO
            htf_trend_up = row['HTF_Close'] > row['HTF_EMA_50']
            htf_trend_down = row['HTF_Close'] < row['HTF_EMA_50']

            # 2. LTF Momentum & Entry (Hourly)
            ltf_rsi = row['RSI_14']
            ltf_macd_hist = row['MACDh_12_26_9']

            # 3. Z-Score Anomaly (Flash Crash Protection)
            z_score = row.get('Z_SCORE', 0)
            if abs(z_score) > 4.0:
                logger.warning(f"FLASH CRASH VETO: {ticker} Z-Score={z_score:.2f}")
                return None

            # 4. Sentiment Veto (NLP)
            sentiment = row.get('SENTIMENT_SCORE', 0.0)

            signal = None
            direction = None

            # Evaluate Long
            if htf_trend_up and ltf_rsi < 35 and ltf_macd_hist > 0:
                if sentiment >= -0.30: # Don't buy if extreme bad news
                    direction = "Long"
                else:
                    logger.info(f"Sentiment Veto: Rejected Long on {ticker} due to NLP={sentiment}")

            # Evaluate Short
            elif htf_trend_down and ltf_rsi > 65 and ltf_macd_hist < 0:
                if sentiment <= 0.30: # Don't sell if extreme good news
                    direction = "Short"
                else:
                    logger.info(f"Sentiment Veto: Rejected Short on {ticker} due to NLP={sentiment}")

            if direction:
                # 5. ML Validation Veto
                features_only = row.drop(['TARGET_LONG', 'TARGET_SHORT'], errors='ignore')
                win_prob = self.ml_validator.predict_probability(features_only)

                if win_prob < 0.60: # Demand 60% historical success probability
                    logger.info(f"ML Veto: Rejected {direction} on {ticker}. Probability: {win_prob:.2f} < 0.60")
                    return None

                # 6. Correlation Veto
                if self.portfolio_mgr.is_vetoed_by_correlation(ticker, direction):
                    return None

                # Signal Approved! Calculate Risk Parameters
                entry_price = row['Close']
                atr = row['ATRr_14']

                # Dynamic ATR Stops (1.5x SL, 3.0x TP)
                if direction == "Long":
                    sl = entry_price - (1.5 * atr)
                    tp = entry_price + (3.0 * atr)
                else:
                    sl = entry_price + (1.5 * atr)
                    tp = entry_price - (3.0 * atr)

                signal = {
                    "ticker": ticker,
                    "direction": direction,
                    "price": entry_price,
                    "sl": sl,
                    "tp": tp,
                    "atr": atr,
                    "ml_prob": win_prob
                }
                return signal

        except KeyError as e:
            logger.error(f"Missing indicator column for {ticker}: {e}")

        return None
