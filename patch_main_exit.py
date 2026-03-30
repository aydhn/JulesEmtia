import re

with open("ed_quant_engine/main.py", "r") as f:
    content = f.read()

# Make sure execution_model is imported
if "apply_execution_costs" not in content:
    content = content.replace("from src.broker import PaperBroker", "from src.broker import PaperBroker\nfrom src.execution_model import apply_execution_costs")

# Let's write a robust regex or string replacement to inject exit cost logic in main.py.
# There are multiple places broker.close_position is called.

def replace_close(match):
    prefix = match.group(1)
    ticker = match.group(2)
    direction = match.group(3)
    current_price = match.group(4)
    reason = match.group(5)

    # We need to construct the logic to apply execution costs before calling close_position
    # Note: In main.py, direction is sometimes known as `direction = trade['direction']`.
    # Let's inject a helper function at the top and call it, or just use apply_execution_costs.
    return match.group(0) # We'll do a simpler replacement.

# We need to modify the open trades loop to apply costs.
old_close = """        if check_flash_crash(df_current):
            log_critical(f"🚨 FLAŞ ÇÖKÜŞ KORUMASI: {ticker} Anormal Fiyat Hareketi. Pozisyon acil kapatılıyor.")
            broker.close_position(trade_id, current_price, "Flash Crash Halt")"""

new_close = """        if check_flash_crash(df_current):
            log_critical(f"🚨 FLAŞ ÇÖKÜŞ KORUMASI: {ticker} Anormal Fiyat Hareketi. Pozisyon acil kapatılıyor.")
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Flash Crash Halt")"""

content = content.replace(old_close, new_close)

old_close2 = """        if vix_panic and ((direction == "Long" and current_price > entry_price) or (direction == "Short" and current_price < entry_price)):
            log_warning(f"VIX Paniği: {ticker} kârda kapatılıyor.")
            broker.close_position(trade_id, current_price, "VIX Panic Lock-In")"""

new_close2 = """        if vix_panic and ((direction == "Long" and current_price > entry_price) or (direction == "Short" and current_price < entry_price)):
            log_warning(f"VIX Paniği: {ticker} kârda kapatılıyor.")
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "VIX Panic Lock-In")"""

content = content.replace(old_close2, new_close2)

old_close3 = """        if hit_sl:
            broker.close_position(trade_id, current_price, "Stop-Loss Hit")"""

new_close3 = """        if hit_sl:
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Stop-Loss Hit")"""

content = content.replace(old_close3, new_close3)

old_close4 = """        if hit_tp:
            broker.close_position(trade_id, current_price, "Take-Profit Hit")"""

new_close4 = """        if hit_tp:
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Take-Profit Hit")"""

content = content.replace(old_close4, new_close4)

# Also fix the panic close
old_panic = """                df = fetch_data_sync(t['ticker'], period="1d", interval="1m")
                current_price = df['Close'].iloc[-1]
                broker.close_position(t['trade_id'], current_price, "Panik (Kapat Hepsi)")"""

new_panic = """                df = fetch_data_sync(t['ticker'], period="1d", interval="1m")
                current_price = df['Close'].iloc[-1]
                # Fallback atr
                exit_price, _, _ = apply_execution_costs(t['ticker'], "Short" if t['direction']=="Long" else "Long", current_price, current_price*0.01, current_price*0.01)
                broker.close_position(t['trade_id'], exit_price, "Panik (Kapat Hepsi)")"""

content = content.replace(old_panic, new_panic)

with open("ed_quant_engine/main.py", "w") as f:
    f.write(content)
