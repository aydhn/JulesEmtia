import pandas as pd
import pandas_ta as ta

df = pd.DataFrame({
    'Open': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],
    'High': [1.1,2.1,3.1,4.1,5.1,6.1,7.1,8.1,9.1,10.1,11.1,12.1,13.1,14.1,15.1,16.1,17.1,18.1,19.1,20.1,21.1,22.1,23.1,24.1,25.1,26.1,27.1,28.1,29.1,30.1],
    'Low': [0.9,1.9,2.9,3.9,4.9,5.9,6.9,7.9,8.9,9.9,10.9,11.9,12.9,13.9,14.9,15.9,16.9,17.9,18.9,19.9,20.9,21.9,22.9,23.9,24.9,25.9,26.9,27.9,28.9,29.9],
    'Close': [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],
    'Volume': [100]*30
})

df.ta.ema(length=50, append=True)
df.ta.ema(length=200, append=True)
df.ta.rsi(length=14, append=True)
df.ta.macd(fast=12, slow=26, signal=9, append=True)
df.ta.atr(length=14, append=True)
df.ta.bbands(length=20, std=2, append=True)

print(df.columns.tolist())
