import pandas as pd
import pandas_ta as ta

df = pd.DataFrame({
    'Open': list(range(1, 101)),
    'High': list(range(2, 102)),
    'Low': list(range(0, 100)),
    'Close': list(range(1, 101)),
    'Volume': [100]*100
})

df.ta.macd(fast=12, slow=26, signal=9, append=True)
df.ta.ema(length=50, append=True)
print(df.columns.tolist())
