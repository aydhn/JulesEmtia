from config import get_spread_for_ticker
from logger import log

def apply_slippage(ticker: str, direction: str, market_price: float, atr: float, avg_atr: float = None) -> float:
    """
    Applies realistic Spread and Volatility-adjusted Slippage to execution prices.
    Returns the worsened execution price.
    """
    base_spread_pct = get_spread_for_ticker(ticker)

    # Base spread cost (half spread)
    half_spread = market_price * (base_spread_pct / 2)

    # Volatility penalty (Slippage)
    slippage_multiplier = 1.0
    if avg_atr and atr > avg_atr * 1.5:
        # High volatility -> Double slippage
        slippage_multiplier = 2.0
        log.warning(f"High volatility detected for {ticker} (ATR={atr:.4f} > Avg={avg_atr:.4f}). Applying 2x slippage.")

    slippage_cost = (market_price * 0.0005) * slippage_multiplier # Base 0.05% slippage

    total_cost = half_spread + slippage_cost

    if direction == "Long":
        return market_price + total_cost  # Pay more to buy
    elif direction == "Short":
        return market_price - total_cost  # Receive less to sell
    else:
        return market_price
