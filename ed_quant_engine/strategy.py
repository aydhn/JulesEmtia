import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from logger import log
from ml_validator import validate_signal_with_ml
from portfolio_manager import is_correlation_veto, check_global_limits, calculate_correlation_matrix
from sentiment_filter import validate_sentiment
from data_loader import fetch_mtf_data, align_mtf_data
from features import add_features
import paper_db

def calculate_kelly_fraction(current_capital: float, max_risk_cap: float = 0.05, kelly_fraction: float = 0.5) -> float:
    """
    Fractional Kelly Criterion for Position Sizing (Phase 15).
    Calculates the optimum % of capital to risk based on historical Win Rate and Reward/Risk Ratio.
    """
    try:
        # Fetch last 50 closed trades
        query = "SELECT pnl, direction FROM trades WHERE status = 'Closed' ORDER BY exit_time DESC LIMIT 50"
        trades = paper_db.fetch_query(query)

        if not trades or len(trades) < 10:
            log.info("Kelly Calculator: Not enough historical trades. Defaulting to 2% fixed risk.")
            return min(0.02, max_risk_cap)

        wins = [t[0] for t in trades if t[0] > 0]
        losses = [t[0] for t in trades if t[0] <= 0]

        if not wins or not losses:
            log.warning("Kelly Calculator: Missing either wins or losses. Defaulting to 2% risk.")
            return min(0.02, max_risk_cap)

        win_rate = len(wins) / len(trades)
        loss_rate = 1.0 - win_rate

        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))

        # Reward/Risk Ratio (b)
        b = avg_win / avg_loss if avg_loss > 0 else 1.0

        # Kelly Formula: f* = (bp - q) / b
        kelly_f = (b * win_rate - loss_rate) / b

        if kelly_f <= 0:
            log.warning(f"Kelly Calculator: Edge lost (f*={kelly_f:.2f}). Defaulting to minimum 0.5% risk.")
            return 0.005 # Minimum survival risk

        # Fractional Kelly (e.g., Half-Kelly) for safety
        fractional_kelly = kelly_f * kelly_fraction

        # Hard Cap (e.g., Never risk more than 5% on a single trade)
        final_risk_pct = min(fractional_kelly, max_risk_cap)

        log.info(f"Kelly Calculated: WR={win_rate:.2f}, R/R={b:.2f} -> Risk={final_risk_pct*100:.2f}%")
        return final_risk_pct

    except Exception as e:
        log.error(f"Failed to calculate Kelly: {e}. Defaulting to 2%.")
        return 0.02


def calculate_position_size(capital: float, entry_price: float, sl_price: float, risk_pct: float) -> float:
    """Calculates the contract/lot size based on the Stop Loss distance (ATR)."""
    risk_amount = capital * risk_pct
    sl_distance = abs(entry_price - sl_price)

    if sl_distance == 0:
        log.warning("Stop Loss distance is zero. Cannot calculate position size.")
        return 0.0

    position_size = risk_amount / sl_distance
    return round(position_size, 4)


def check_signals(ticker: str, df: pd.DataFrame, current_capital: float, open_trades: list, corr_matrix: pd.DataFrame) -> Optional[Dict]:
    """
    Core Strategy Engine (Phase 4 & 16)
    Evaluates Confluence: HTF Trend + LTF Oscillators + Dynamic ATR Stops + Global Vetoes.
    Returns a dictionary with execution details if a valid signal is found, else None.
    """
    if df.empty or len(df) < 2:
        return None

    try:
        # STRICKT LOOKAHEAD BIAS PREVENTION: Use the *previous* closed candle for signal logic
        prev_row = df.iloc[-2]
        current_row = df.iloc[-1]

        # Determine HTF (Daily) Trend direction
        htf_trend_up = prev_row.get('close_htf', 0) > prev_row.get('EMA_50_htf', 0)
        htf_trend_down = prev_row.get('close_htf', 0) < prev_row.get('EMA_50_htf', 0)

        # Base LTF (Hourly) Conditions
        # Long: Price > 50 EMA, RSI crossing above 30 (Oversold), MACD Hist > 0
        ltf_long = (
            (prev_row['close'] > prev_row['EMA_50']) and
            (prev_row['RSI_14'] > 30 and df.iloc[-3]['RSI_14'] <= 30) and
            (prev_row['MACD_Hist'] > 0)
        )

        # Short: Price < 50 EMA, RSI crossing below 70 (Overbought), MACD Hist < 0
        ltf_short = (
            (prev_row['close'] < prev_row['EMA_50']) and
            (prev_row['RSI_14'] < 70 and df.iloc[-3]['RSI_14'] >= 70) and
            (prev_row['MACD_Hist'] < 0)
        )

        signal = None

        # Confluence Check (MTF Agreement)
        if ltf_long and htf_trend_up:
            signal = "Long"
        elif ltf_short and htf_trend_down:
            signal = "Short"

        if not signal:
            return None

        # -----------------------------------------------------
        # VETO CHAIN (Phase 11, Phase 18, Phase 20)
        # -----------------------------------------------------

        # 1. NLP Sentiment Veto
        if not validate_sentiment(ticker, signal):
            return None

        # 2. ML Probability Veto
        if not validate_signal_with_ml(prev_row.to_dict()):
            return None

        # 3. Correlation Risk Veto
        if is_correlation_veto(ticker, signal, open_trades, corr_matrix):
            return None

        # -----------------------------------------------------
        # JP Morgan Risk Algısı: Dynamic ATR Risk Management
        # -----------------------------------------------------
        entry_price = current_row['close']
        atr = prev_row['ATR_14']

        if pd.isna(atr) or atr == 0:
            log.warning(f"Invalid ATR for {ticker}, skipping signal.")
            return None

        # SL = 1.5 ATR, TP = 3.0 ATR (1:2 Risk/Reward)
        if signal == "Long":
            sl_price = entry_price - (1.5 * atr)
            tp_price = entry_price + (3.0 * atr)
        else:
            sl_price = entry_price + (1.5 * atr)
            tp_price = entry_price - (3.0 * atr)

        # -----------------------------------------------------
        # Position Sizing (Fractional Kelly)
        # -----------------------------------------------------
        risk_pct = calculate_kelly_fraction(current_capital)
        position_size = calculate_position_size(current_capital, entry_price, sl_price, risk_pct)

        if position_size <= 0:
            log.warning(f"Calculated position size <= 0 for {ticker}, skipping trade.")
            return None

        log.info(f"✅ HIGH CONVICTION SIGNAL [{ticker} {signal}]: Entry {entry_price:.4f}, SL {sl_price:.4f}, TP {tp_price:.4f}, Lot {position_size:.2f}")

        return {
            "ticker": ticker,
            "direction": signal,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "position_size": position_size,
            "risk_pct": risk_pct
        }

    except Exception as e:
        log.error(f"Error evaluating strategy for {ticker}: {e}")
        return None
