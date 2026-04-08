with open("ed_quant_engine/src/features.py", "r") as f:
    content = f.read()

new_indicators = """
        # MFI (Money Flow Index)
        mfi = ta.mfi(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], ltf_df['Volume'], length=14)
        if mfi is not None and not mfi.empty:
            ltf_df['MFI_14'] = mfi

        # CMF (Chaikin Money Flow)
        cmf = ta.cmf(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], ltf_df['Volume'], length=20)
        if cmf is not None and not cmf.empty:
            ltf_df['CMF_20'] = cmf

        # Supertrend
        supertrend = ta.supertrend(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], length=7, multiplier=3.0)
        if supertrend is not None and not supertrend.empty:
            ltf_df = pd.concat([ltf_df, supertrend], axis=1)

        # Keltner Channels
        kc = ta.kc(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], length=20, scalar=1.5)
        if kc is not None and not kc.empty:
            ltf_df = pd.concat([ltf_df, kc], axis=1)
"""

content = content.replace("        # Uyumsuzluk (Divergence) Detection (RSI & MACD)", new_indicators + "\n        # Uyumsuzluk (Divergence) Detection (RSI & MACD)")

new_divergence = """
        if 'MFI_14' in ltf_df.columns:
            mfi_diff = ltf_df['MFI_14'].diff(periods=10)
            ltf_df['Bullish_Div_MFI'] = (ltf_df['Price_Diff'] < 0) & (mfi_diff > 0) & (ltf_df['MFI_14'] < 40)
            ltf_df['Bearish_Div_MFI'] = (ltf_df['Price_Diff'] > 0) & (mfi_diff < 0) & (ltf_df['MFI_14'] > 60)
"""

content = content.replace("        # MTF Merge Process (backward direction to ensure we only get PAST data)", new_divergence + "\n        # MTF Merge Process (backward direction to ensure we only get PAST data)")

with open("ed_quant_engine/src/features.py", "w") as f:
    f.write(content)
