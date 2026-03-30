with open('ed_quant_engine/main.py', 'r') as f:
    content = f.read()

content = content.replace("returns_df = pd.DataFrame()", "returns_df = await portfolio_manager.fetch_daily_returns_matrix(flat_tickers)")

with open('ed_quant_engine/main.py', 'w') as f:
    f.write(content)
