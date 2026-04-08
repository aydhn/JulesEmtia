import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

def calculate_mtf_features(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Phase 16: MTF Data Synchronization (Lookahead Bias Protection).
    Phase 3: More Indicators (ADX, Bollinger) & Divergences.
    """
    if htf_df is None or htf_df.empty or ltf_df is None or ltf_df.empty:
        return pd.DataFrame()

    try:
        # Calculate HTF Features BEFORE merge to ensure math accuracy
        htf_df = htf_df.copy()

        # Trend
        htf_df['EMA_50'] = ta.ema(htf_df['Close'], length=50)
        htf_df['EMA_200'] = ta.ema(htf_df['Close'], length=200)

        # MACD
        macd_htf = ta.macd(htf_df['Close'])
        if macd_htf is not None and not macd_htf.empty:
            htf_df = pd.concat([htf_df, macd_htf], axis=1)

        # ADX
        adx_htf = ta.adx(htf_df['High'], htf_df['Low'], htf_df['Close'])
        if adx_htf is not None and not adx_htf.empty:
            htf_df = pd.concat([htf_df, adx_htf], axis=1)

        # Shift HTF by 1 to prevent lookahead bias!
        # The closing data of day T is only available on day T+1
        htf_shifted = htf_df.shift(1).reset_index()

        if 'Date' not in htf_shifted.columns and 'Datetime' in htf_shifted.columns:
            htf_shifted.rename(columns={'Datetime': 'Date'}, inplace=True)

        # Ensure timezone stripping for merge_asof
        if pd.api.types.is_datetime64tz_dtype(htf_shifted['Date']):
            htf_shifted['Date'] = htf_shifted['Date'].dt.tz_localize(None)


        # Calculate LTF Features
        ltf_df = ltf_df.copy()

        # Base Indicators
        ltf_df['EMA_50'] = ta.ema(ltf_df['Close'], length=50)
        ltf_df['RSI_14'] = ta.rsi(ltf_df['Close'], length=14)
        ltf_df['ATR_14'] = ta.atr(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], length=14)

        macd_ltf = ta.macd(ltf_df['Close'])
        if macd_ltf is not None and not macd_ltf.empty:
            ltf_df = pd.concat([ltf_df, macd_ltf], axis=1)


        bbands = ta.bbands(ltf_df['Close'])
        if bbands is not None and not bbands.empty:
            ltf_df = pd.concat([ltf_df, bbands], axis=1)

        # Stochastic
        stoch = ta.stoch(ltf_df['High'], ltf_df['Low'], ltf_df['Close'])
        if stoch is not None and not stoch.empty:
            ltf_df = pd.concat([ltf_df, stoch], axis=1)

        # OBV
        obv = ta.obv(ltf_df['Close'], ltf_df['Volume'])
        if obv is not None and not obv.empty:
            ltf_df = pd.concat([ltf_df, obv], axis=1)



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

        # Uyumsuzluk (Divergence) Detection (RSI & MACD)
        ltf_df['Price_Diff'] = ltf_df['Close'].diff(periods=10)

        if 'RSI_14' in ltf_df.columns:
            rsi_diff = ltf_df['RSI_14'].diff(periods=10)
            ltf_df['Bullish_Div_RSI'] = (ltf_df['Price_Diff'] < 0) & (rsi_diff > 0) & (ltf_df['RSI_14'] < 40)
            ltf_df['Bearish_Div_RSI'] = (ltf_df['Price_Diff'] > 0) & (rsi_diff < 0) & (ltf_df['RSI_14'] > 60)


        if 'MACDh_12_26_9' in ltf_df.columns:
            macd_diff = ltf_df['MACDh_12_26_9'].diff(periods=10)
            ltf_df['Bullish_Div_MACD'] = (ltf_df['Price_Diff'] < 0) & (macd_diff > 0) & (ltf_df['MACDh_12_26_9'] < 0)
            ltf_df['Bearish_Div_MACD'] = (ltf_df['Price_Diff'] > 0) & (macd_diff < 0) & (ltf_df['MACDh_12_26_9'] > 0)

        stoch_k_col = [c for c in ltf_df.columns if c.startswith('STOCHk_')]
        if stoch_k_col:
            stoch_k = ltf_df[stoch_k_col[0]]
            stoch_diff = stoch_k.diff(periods=10)
            ltf_df['Bullish_Div_Stoch'] = (ltf_df['Price_Diff'] < 0) & (stoch_diff > 0) & (stoch_k < 20)
            ltf_df['Bearish_Div_Stoch'] = (ltf_df['Price_Diff'] > 0) & (stoch_diff < 0) & (stoch_k > 80)



        if 'MFI_14' in ltf_df.columns:
            mfi_diff = ltf_df['MFI_14'].diff(periods=10)
            ltf_df['Bullish_Div_MFI'] = (ltf_df['Price_Diff'] < 0) & (mfi_diff > 0) & (ltf_df['MFI_14'] < 40)
            ltf_df['Bearish_Div_MFI'] = (ltf_df['Price_Diff'] > 0) & (mfi_diff < 0) & (ltf_df['MFI_14'] > 60)

        # MTF Merge Process (backward direction to ensure we only get PAST data)
        ltf_reset = ltf_df.reset_index()
        if 'Date' not in ltf_reset.columns and 'Datetime' in ltf_reset.columns:
            ltf_reset.rename(columns={'Datetime': 'Date'}, inplace=True)

        if pd.api.types.is_datetime64tz_dtype(ltf_reset['Date']):
            ltf_reset['Date'] = ltf_reset['Date'].dt.tz_localize(None)

        merged_df = pd.merge_asof(
            ltf_reset.sort_values('Date'),
            htf_shifted.sort_values('Date'),
            on='Date',
            direction='backward',
            suffixes=('', '_HTF')
        )

        merged_df.set_index('Date', inplace=True)
        return merged_df

    except Exception as e:
        logger.error(f"Error calculating MTF features: {e}")
        return pd.DataFrame()
