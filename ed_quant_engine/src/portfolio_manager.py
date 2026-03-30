import pandas as pd
from typing import Dict, Any, List
from src.paper_db import get_open_trades, get_closed_trades
from src.logger import get_logger

logger = get_logger("portfolio_manager")

MAX_OPEN_POSITIONS = 4
MAX_GLOBAL_RISK_PCT = 0.06 # Maximum 6% of total account balance at risk at any given time
CORRELATION_THRESHOLD = 0.75

def calculate_correlation_matrix(df_universe: Dict[str, pd.DataFrame], lookback: int = 60) -> pd.DataFrame:
    """Calculates a rolling Pearson correlation matrix for the past N days."""
    close_prices = {}

    for ticker, df in df_universe.items():
        if not df.empty and 'Close' in df.columns:
            close_prices[ticker] = df['Close'].tail(lookback)

    df_close = pd.DataFrame(close_prices)
    df_close = df_close.ffill().bfill()

    if df_close.empty:
        return pd.DataFrame()

    return df_close.corr()

def check_correlation_veto(new_ticker: str, new_direction: str, corr_matrix: pd.DataFrame) -> bool:
    """Vetoes a trade if it duplicates exposure with a highly correlated open position."""
    if corr_matrix.empty or new_ticker not in corr_matrix.columns:
        return False

    open_trades = get_open_trades()
    if not open_trades:
        return False

    for trade in open_trades:
        existing_ticker = trade['ticker']
        existing_direction = trade['direction']

        if existing_ticker in corr_matrix.columns:
            corr_val = corr_matrix.loc[new_ticker, existing_ticker]

            # If highly correlated (> 0.75) and same direction -> Risk Duplication Veto
            if corr_val > CORRELATION_THRESHOLD and new_direction == existing_direction:
                logger.info(f"Correlation Veto: {new_ticker} rejected. Highly correlated ({corr_val:.2f}) with open {existing_ticker} {existing_direction} position.")
                return True

            # If highly negatively correlated (< -0.75) and opposite direction -> Also Risk Duplication (Hedge but doubled exposure)
            elif corr_val < -CORRELATION_THRESHOLD and new_direction != existing_direction:
                logger.info(f"Negative Correlation Veto: {new_ticker} rejected. Doubling exposure against {existing_ticker}.")
                return True

    return False

def calculate_kelly_fraction(b: float, p: float, q: float) -> float:
    """Calculates the Kelly Criterion fraction f* = (bp - q) / b"""
    if b <= 0: return 0.0
    f_star = (b * p - q) / b
    return max(0.0, f_star)

def get_dynamic_position_size(ticker: str, account_balance: float, entry_price: float, sl_price: float) -> float:
    """Calculates position size using Fractional Kelly Criterion and Stop-Loss distance."""

    # 1. Fetch historical performance for Kelly variables
    closed_trades = get_closed_trades()

    p = 0.50 # Default win rate
    b = 1.50 # Default reward/risk

    if len(closed_trades) > 10:
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] < 0]

        if len(winning_trades) > 0 and len(losing_trades) > 0:
            p = len(winning_trades) / len(closed_trades)
            avg_win = sum([t['pnl'] for t in winning_trades]) / len(winning_trades)
            avg_loss = abs(sum([t['pnl'] for t in losing_trades]) / len(losing_trades))

            if avg_loss > 0:
                b = avg_win / avg_loss

    q = 1.0 - p

    # 2. Calculate Kelly
    f_star = calculate_kelly_fraction(b, p, q)

    # 3. Apply JP Morgan Risk Safety Buffer (Half-Kelly)
    fractional_kelly = f_star / 2.0

    # 4. Cap limits
    max_risk_pct = 0.04 # Hard cap: Max 4% of account per trade
    if fractional_kelly > max_risk_pct:
        fractional_kelly = max_risk_pct
    elif fractional_kelly <= 0:
        fractional_kelly = 0.005 # Minimum 0.5% risk if Kelly suggests no trade (to keep system alive and learning)

    # Calculate absolute risk amount
    risk_amount = account_balance * fractional_kelly

    # 5. Determine Position Size based on ATR/SL distance
    sl_distance = abs(entry_price - sl_price)

    if sl_distance == 0:
        logger.error("Stop Loss distance is zero. Cannot calculate position size.")
        return 0.0

    lot_size = risk_amount / sl_distance

    logger.debug(f"Kelly sizing for {ticker}: WinRate={p:.2f}, R/R={b:.2f}, Kelly={f_star:.3f}, Fraction={fractional_kelly:.3f}, Lot={lot_size:.4f}")

    return lot_size

def check_global_exposure(new_risk_pct: float) -> bool:
    """Returns True if global portfolio limits are breached (VETO)."""
    open_trades = get_open_trades()

    if len(open_trades) >= MAX_OPEN_POSITIONS:
        logger.info(f"Capacity Veto: Max open positions ({MAX_OPEN_POSITIONS}) reached.")
        return True

    # In a full system, you would sum the current dynamic risk of all open trades.
    # For now, we enforce a simple count limit and Kelly handles individual caps.

    return False
