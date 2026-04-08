import pandas as pd
import numpy as np
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

def calculate_mtf_features(htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> pd.DataFrame:
    """
    Phase 16: MTF Data Synchronization (Lookahead Bias Protection).
    Phase 3: More Indicators (ADX, Bollinger, CCI, Parabolic SAR) & Divergences.
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
        ltf_df['EMA_200'] = ta.ema(ltf_df['Close'], length=200)
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

        # CCI (Commodity Channel Index)
        cci = ta.cci(ltf_df['High'], ltf_df['Low'], ltf_df['Close'], length=20)
        if cci is not None and not cci.empty:
            ltf_df['CCI_20'] = cci

        # Parabolic SAR
        psar = ta.psar(ltf_df['High'], ltf_df['Low'], ltf_df['Close'])
        if psar is not None and not psar.empty:
            ltf_df = pd.concat([ltf_df, psar], axis=1)

        # Uyumsuzluk (Divergence) Detection (RSI, MACD, Stochastic)
        # Refined divergence to check local extremums using rolling windows
        lookback = 10
        ltf_df['Price_Low_Min'] = ltf_df['Low'].rolling(window=lookback).min()
        ltf_df['Price_High_Max'] = ltf_df['High'].rolling(window=lookback).max()

        if 'RSI_14' in ltf_df.columns:
            ltf_df['RSI_Min'] = ltf_df['RSI_14'].rolling(window=lookback).min()
            ltf_df['RSI_Max'] = ltf_df['RSI_14'].rolling(window=lookback).max()

            # Bullish Div: Price makes lower low, RSI makes higher low
            ltf_df['Bullish_Div_RSI'] = (ltf_df['Low'] <= ltf_df['Price_Low_Min']) & (ltf_df['RSI_14'] > ltf_df['RSI_Min']) & (ltf_df['RSI_14'] < 40)

            # Bearish Div: Price makes higher high, RSI makes lower high
            ltf_df['Bearish_Div_RSI'] = (ltf_df['High'] >= ltf_df['Price_High_Max']) & (ltf_df['RSI_14'] < ltf_df['RSI_Max']) & (ltf_df['RSI_14'] > 60)

        if 'MACDh_12_26_9' in ltf_df.columns:
            ltf_df['MACD_Min'] = ltf_df['MACDh_12_26_9'].rolling(window=lookback).min()
            ltf_df['MACD_Max'] = ltf_df['MACDh_12_26_9'].rolling(window=lookback).max()
            ltf_df['Bullish_Div_MACD'] = (ltf_df['Low'] <= ltf_df['Price_Low_Min']) & (ltf_df['MACDh_12_26_9'] > ltf_df['MACD_Min']) & (ltf_df['MACDh_12_26_9'] < 0)
            ltf_df['Bearish_Div_MACD'] = (ltf_df['High'] >= ltf_df['Price_High_Max']) & (ltf_df['MACDh_12_26_9'] < ltf_df['MACD_Max']) & (ltf_df['MACDh_12_26_9'] > 0)

        stoch_k_col = [c for c in ltf_df.columns if c.startswith('STOCHk_')]
        if stoch_k_col:
            stoch_k = ltf_df[stoch_k_col[0]]
            ltf_df['Stoch_Min'] = stoch_k.rolling(window=lookback).min()
            ltf_df['Stoch_Max'] = stoch_k.rolling(window=lookback).max()
            ltf_df['Bullish_Div_Stoch'] = (ltf_df['Low'] <= ltf_df['Price_Low_Min']) & (stoch_k > ltf_df['Stoch_Min']) & (stoch_k < 20)
            ltf_df['Bearish_Div_Stoch'] = (ltf_df['High'] >= ltf_df['Price_High_Max']) & (stoch_k < ltf_df['Stoch_Max']) & (stoch_k > 80)

        if 'MFI_14' in ltf_df.columns:
            ltf_df['MFI_Min'] = ltf_df['MFI_14'].rolling(window=lookback).min()
            ltf_df['MFI_Max'] = ltf_df['MFI_14'].rolling(window=lookback).max()
            ltf_df['Bullish_Div_MFI'] = (ltf_df['Low'] <= ltf_df['Price_Low_Min']) & (ltf_df['MFI_14'] > ltf_df['MFI_Min']) & (ltf_df['MFI_14'] < 40)
            ltf_df['Bearish_Div_MFI'] = (ltf_df['High'] >= ltf_df['Price_High_Max']) & (ltf_df['MFI_14'] < ltf_df['MFI_Max']) & (ltf_df['MFI_14'] > 60)

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

        # Cleanup temporary rolling columns
        cols_to_drop = ['Price_Low_Min', 'Price_High_Max', 'RSI_Min', 'RSI_Max', 'MACD_Min', 'MACD_Max', 'Stoch_Min', 'Stoch_Max', 'MFI_Min', 'MFI_Max']
        cols_to_drop = [c for c in cols_to_drop if c in merged_df.columns]
        merged_df.drop(columns=cols_to_drop, inplace=True)

        return merged_df

    except Exception as e:
        logger.error(f"Error calculating MTF features: {e}")
        return pd.DataFrame()
