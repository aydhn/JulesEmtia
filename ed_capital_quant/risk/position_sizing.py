"""
ED Capital Quant Engine - Position Sizing Module
Dynamic risk-based position allocation.
"""
def calculate_position_size(risk_amount: float, entry_price: float, sl_price: float) -> float:
    """Calculate the number of units to trade based on risk and stop loss distance."""
    if sl_price == entry_price:
        return 0.0

    sl_distance = abs(entry_price - sl_price)

    # Position Size = Risk Amount / Stop Loss Distance (Per Unit)
    position_size = risk_amount / sl_distance

    # Cap position size logically if needed
    if position_size < 0.01:
        position_size = 0.01

    return round(position_size, 4)
