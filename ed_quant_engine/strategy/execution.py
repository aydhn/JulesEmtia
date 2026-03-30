from core.config import TICKERS

def get_base_spread(ticker: str) -> float:
    # Simulating base spreads percentage
    if ticker in TICKERS['Metals'] or ticker in TICKERS['Energy']:
        return 0.0002 # 0.02%
    elif ticker in TICKERS['Forex']:
        return 0.0010 # 0.10%
    else:
        return 0.0005 # 0.05%

def calculate_slippage(atr: float, avg_atr: float, base_spread: float) -> float:
    # If volatility is 50% higher than average, double the slippage
    if atr > avg_atr * 1.5:
        return base_spread * 2.0
    return base_spread

def execute_cost_model(ticker: str, entry_price: float, atr: float, avg_atr: float, direction: str) -> tuple:
    base_spread = get_base_spread(ticker)
    slippage_pct = calculate_slippage(atr, avg_atr, base_spread)

    cost_val = entry_price * (base_spread / 2.0 + slippage_pct)

    if direction == 'Long':
        adjusted_entry = entry_price + cost_val
    else:
        adjusted_entry = entry_price - cost_val

    return adjusted_entry, cost_val
