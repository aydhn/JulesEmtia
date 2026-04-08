import yfinance as yf
vix = yf.download("^VIX", period="5d", progress=False)['Close'].iloc[-1]
# Actually, depending on the yfinance version, `vix` could be a pandas Series or a scalar float.
if isinstance(vix, pd.Series):
    val = float(vix.iloc[0])
else:
    val = float(vix)
print(val)
