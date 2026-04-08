with open("ed_quant_engine/src/strategy.py", "r") as f:
    content = f.read()

new_logic = """
        # Base Conditions with Confluence
        # Extract new indicators
        mfi_col = [c for c in mtf_df.columns if c.startswith('MFI_')]
        ltf_mfi = prev_candle[mfi_col[0]] if mfi_col else 50

        cmf_col = [c for c in mtf_df.columns if c.startswith('CMF_')]
        ltf_cmf = prev_candle[cmf_col[0]] if cmf_col else 0

        # SUPERTd contains direction (1 for bullish, -1 for bearish)
        super_col = [c for c in mtf_df.columns if c.startswith('SUPERTd_')]
        ltf_supertrend_dir = prev_candle[super_col[0]] if super_col else 0

        div_bull_mfi = prev_candle.get('Bullish_Div_MFI', False)
        div_bear_mfi = prev_candle.get('Bearish_Div_MFI', False)

        # Long requires: (RSI oversold OR MACD positive OR Stochastic oversold OR MFI oversold OR any bullish divergence) AND OBV trend up AND Close > EMA50 AND Supertrend Bullish AND CMF > 0
        ltf_bull_cond = (
            (ltf_rsi < 35 or ltf_macd > 0 or stoch_k < 20 or ltf_mfi < 35 or div_bull_rsi or div_bull_stoch or div_bull_macd or div_bull_mfi)
            and obv_trend_up
            and (ltf_close > ltf_ema50)
            and (ltf_supertrend_dir == 1 or not super_col)
            and (ltf_cmf > 0 or not cmf_col)
        )

        # Short requires: (RSI overbought OR MACD negative OR Stochastic overbought OR MFI overbought OR any bearish divergence) AND OBV trend down AND Close < EMA50 AND Supertrend Bearish AND CMF < 0
        ltf_bear_cond = (
            (ltf_rsi > 65 or ltf_macd < 0 or stoch_k > 80 or ltf_mfi > 65 or div_bear_rsi or div_bear_stoch or div_bear_macd or div_bear_mfi)
            and obv_trend_down
            and (ltf_close < ltf_ema50)
            and (ltf_supertrend_dir == -1 or not super_col)
            and (ltf_cmf < 0 or not cmf_col)
        )
"""

old_logic = """
        # Base Conditions with Confluence
        # Long requires: (RSI oversold OR MACD positive OR Stochastic oversold OR any bullish divergence) AND OBV trend up AND Close > EMA50
        ltf_bull_cond = (ltf_rsi < 35 or ltf_macd > 0 or stoch_k < 20 or div_bull_rsi or div_bull_stoch or div_bull_macd) and obv_trend_up and (ltf_close > ltf_ema50)

        # Short requires: (RSI overbought OR MACD negative OR Stochastic overbought OR any bearish divergence) AND OBV trend down AND Close < EMA50
        ltf_bear_cond = (ltf_rsi > 65 or ltf_macd < 0 or stoch_k > 80 or div_bear_rsi or div_bear_stoch or div_bear_macd) and obv_trend_down and (ltf_close < ltf_ema50)
"""

content = content.replace(old_logic.strip(), new_logic.strip())

with open("ed_quant_engine/src/strategy.py", "w") as f:
    f.write(content)
