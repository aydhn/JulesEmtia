from db.paper_broker import PaperBroker
from core.logger import get_logger

log = get_logger()

def check_open_positions(broker: PaperBroker, current_prices: dict, current_atrs: dict):
    open_positions = broker.get_open_positions()

    for pos in open_positions:
        trade_id = pos['trade_id']
        ticker = pos['ticker']
        direction = pos['direction']
        entry_price = pos['entry_price']
        sl_price = pos['sl_price']
        tp_price = pos['tp_price']

        if ticker not in current_prices:
            continue

        current_price = current_prices[ticker]
        atr = current_atrs.get(ticker, 0.0)

        if direction == 'Long':
            # Check Stop Loss / Take Profit
            if current_price <= sl_price:
                pnl = (sl_price - entry_price) * pos['position_size']
                broker.close_position(trade_id, sl_price, pnl, 'SL Hit')
                continue
            elif current_price >= tp_price:
                pnl = (tp_price - entry_price) * pos['position_size']
                broker.close_position(trade_id, tp_price, pnl, 'TP Hit')
                continue

            # Trailing Stop & Breakeven logic
            # Breakeven if price moved 1 ATR in our favor
            if current_price >= entry_price + atr and sl_price < entry_price:
                broker.modify_trailing_stop(trade_id, entry_price)
                log.info(f"🔒 Risk Sıfırlandı: {ticker} SL seviyesi giriş fiyatına çekildi")

            # Trailing stop: 1.5 ATR behind current price if better than current SL
            new_sl = current_price - (1.5 * atr)
            if new_sl > sl_price:
                broker.modify_trailing_stop(trade_id, new_sl)

        elif direction == 'Short':
            # Check Stop Loss / Take Profit
            if current_price >= sl_price:
                pnl = (entry_price - sl_price) * pos['position_size']
                broker.close_position(trade_id, sl_price, pnl, 'SL Hit')
                continue
            elif current_price <= tp_price:
                pnl = (entry_price - tp_price) * pos['position_size']
                broker.close_position(trade_id, tp_price, pnl, 'TP Hit')
                continue

            # Breakeven if price moved 1 ATR in our favor
            if current_price <= entry_price - atr and sl_price > entry_price:
                broker.modify_trailing_stop(trade_id, entry_price)
                log.info(f"🔒 Risk Sıfırlandı: {ticker} SL seviyesi giriş fiyatına çekildi")

            # Trailing stop: 1.5 ATR above current price if better than current SL
            new_sl = current_price + (1.5 * atr)
            if new_sl < sl_price:
                broker.modify_trailing_stop(trade_id, new_sl)
