class ExecutionSimulator:
    def __init__(self):
        self.base_spreads = {
            "Metals": 0.0002,
            "Forex_TRY": 0.0010,
            "Energy": 0.0005,
            "Agriculture": 0.0008
        }

    def get_execution_price_and_cost(self, asset_class: str, price: float, atr: float, direction: str) -> tuple:
        spread = self.base_spreads.get(asset_class, 0.0005)

        # Volatility-based dynamic slippage
        slippage = (atr / price) * 0.15
        total_cost_percentage = (float(spread) / 2) + slippage
        cost_value = price * total_cost_percentage

        executed_price = price + cost_value if direction == "Long" else price - cost_value
        return executed_price, cost_value
