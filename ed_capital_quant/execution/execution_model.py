from core.config import BASE_SPREADS

def calculate_execution_price(price: float, atr: float, category: str, direction: str) -> float:
    base_spread = BASE_SPREADS.get(category, 0.0005)
    slippage = (atr / price) * 0.1 * price
    total_cost = (price * base_spread / 2) + slippage

    if direction == "Long":
        return price + total_cost
    else:
        return price - total_cost
