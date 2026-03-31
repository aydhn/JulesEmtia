import pandas as pd
import pandas_ta as ta
df = pd.DataFrame({'Close': list(range(100))})
df.ta.bbands(length=20, std=2, append=True)
print(df.columns.tolist())
