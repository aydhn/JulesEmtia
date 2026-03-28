import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from core.logger import setup_logger
from core.config import MAX_OPEN_POSITIONS, MAX_GLOBAL_EXPOSURE_PCT, MAX_RISK_PER_TRADE_PCT, CORRELATION_THRESHOLD, UNIVERSE, KELLY_FRACTION

logger = setup_logger("portfolio_manager")

class PortfolioManager:
    """
    Advanced Portfolio Allocation & Correlation Engine (Phase 11 & 15).
    Enforces risk limits, correlation vetos, fractional Kelly Criterion, and Execution Modeling.
    """
    def __init__(self, broker):
        self.broker = broker
        self.correlation_matrix = pd.DataFrame()

    def update_correlation_matrix(self, history_data: Dict[str, pd.DataFrame], lookback: int = 30):
        """
        Calculates a dynamic rolling Pearson Correlation Matrix over the last N days.
        """
        logger.info("Updating Correlation Matrix...")
        closes = {}
        for ticker, htf_df in history_data.items():
            if htf_df is not None and len(htf_df) >= lookback:
                # Get the 'close' column, or handle multi-index if needed
                if isinstance(htf_df.columns, pd.MultiIndex):
                     closes[ticker] = htf_df['Close'].iloc[-lookback:]
                else:
                     closes[ticker] = htf_df['close'].iloc[-lookback:]

        if not closes:
            return

        df_closes = pd.DataFrame(closes)
        self.correlation_matrix = df_closes.corr(method='pearson')
        logger.debug(f"Correlation Matrix:\n{self.correlation_matrix}")

    def check_correlation_veto(self, new_ticker: str, new_direction: str, open_positions: List[Dict]) -> bool:
        """
        Vetos trade if highly correlated with existing positions in the same direction.
        """
        if self.correlation_matrix.empty or new_ticker not in self.correlation_matrix.columns:
            return True # Allow if no data

        for pos in open_positions:
            existing_ticker = pos['ticker']
            existing_direction = pos['direction']

            if existing_ticker in self.correlation_matrix.columns:
                corr = self.correlation_matrix.loc[new_ticker, existing_ticker]

                # High positive correlation AND same direction -> Risk duplication
                if corr >= CORRELATION_THRESHOLD and new_direction == existing_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} is highly correlated ({corr:.2f}) with {existing_ticker} ({existing_direction})")
                    return False

                # High negative correlation AND opposite direction -> Risk duplication
                if corr <= -CORRELATION_THRESHOLD and new_direction != existing_direction:
                    logger.warning(f"Correlation Veto: {new_ticker} is highly negatively correlated ({corr:.2f}) with {existing_ticker} ({existing_direction})")
                    return False

        return True

    def calculate_kelly_fraction(self) -> float:
        """
        Calculates Fractional Kelly Criterion based on recent closed trades.
        Returns the percentage of the account to risk (f* / 2).
        """
        closed_trades = self.broker.get_closed_positions()

        # Minimum safe fraction if no history
        safe_fraction = 0.01

        if len(closed_trades) < 20: # Need statistically significant history
            return safe_fraction

        df = pd.DataFrame(closed_trades)
        wins = df[df['pnl'] > 0]
        losses = df[df['pnl'] <= 0]

        win_rate = len(wins) / len(df)
        loss_rate = 1.0 - win_rate

        if win_rate == 0 or len(losses) == 0:
            return safe_fraction

        avg_win = wins['pnl'].mean()
        avg_loss = abs(losses['pnl'].mean())

        if avg_loss == 0:
            return safe_fraction

        win_loss_ratio = avg_win / avg_loss

        # Basic Kelly Formula: f = p - (q / b)
        kelly_pct = win_rate - (loss_rate / win_loss_ratio)

        if kelly_pct <= 0:
            logger.warning(f"Kelly Criterion Negative ({kelly_pct:.2f}). Strategy edge lost. Reverting to safe fraction.")
            return safe_fraction

        # Fractional Kelly (JP Morgan Risk Profile)
        fractional_kelly = kelly_pct * KELLY_FRACTION

        # Hard Cap Protection
        final_risk_pct = min(fractional_kelly, MAX_RISK_PER_TRADE_PCT)

        logger.info(f"Calculated Kelly: {kelly_pct:.2%}, Applied Fractional Risk: {final_risk_pct:.2%}")
        return final_risk_pct

    def simulate_execution_costs(self, ticker: str, direction: str, raw_price: float, atr: float, volatility_spike: bool = False) -> float:
        """
        Phase 21: Applies Dynamic Spread and ATR-Adjusted Slippage.
        """
        universe_info = UNIVERSE.get(ticker, {"base_spread_pct": 0.0005})
        base_spread = universe_info["base_spread_pct"]

        # Volatility penalty: Double slippage if ATR is spiking
        slippage_mult = 2.0 if volatility_spike else 1.0
        slippage_pct = (atr / raw_price) * 0.1 * slippage_mult # Assuming 10% of ATR is standard slippage

        total_cost_pct = (base_spread / 2) + slippage_pct

        if direction == "Long":
            executed_price = raw_price * (1 + total_cost_pct)
        else:
            executed_price = raw_price * (1 - total_cost_pct)

        logger.debug(f"[{ticker}] Execution Modeling: Raw={raw_price:.4f}, Executed={executed_price:.4f}, Cost={(total_cost_pct*100):.3f}%")
        return executed_price

    def size_position(self, ticker: str, direction: str, sl_price: float, entry_price: float) -> Tuple[bool, float, str]:
        """
        Calculates position size using Kelly Criterion and enforces Global Exposure limits.
        """
        open_positions = self.broker.get_open_positions()

        if len(open_positions) >= MAX_OPEN_POSITIONS:
            return False, 0.0, "Global Limit Veto: Max open positions reached."

        account_balance = self.broker.get_account_balance()

        # Risk percentage based on Kelly
        risk_pct = self.calculate_kelly_fraction()
        capital_at_risk = account_balance * risk_pct

        # Calculate Lot Size
        stop_distance = abs(entry_price - sl_price)
        if stop_distance == 0:
            return False, 0.0, "Invalid stop distance (0)."

        position_size = capital_at_risk / stop_distance

        # Global Exposure Check (Don't use the whole account)
        total_exposure = sum([p['position_size'] * p['entry_price'] for p in open_positions])
        new_exposure = position_size * entry_price

        if (total_exposure + new_exposure) / account_balance > MAX_GLOBAL_EXPOSURE_PCT:
             # Reduce position size to fit max exposure
             available_exposure = (account_balance * MAX_GLOBAL_EXPOSURE_PCT) - total_exposure
             if available_exposure <= 0:
                 return False, 0.0, "Global Limit Veto: Max portfolio exposure reached."

             position_size = available_exposure / entry_price
             logger.warning(f"Position size reduced to fit global exposure limits. New size: {position_size:.4f}")

        return True, position_size, "Approved"
