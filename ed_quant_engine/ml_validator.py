import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
import joblib
import os
from ed_quant_engine.logger import log
from ed_quant_engine.config import MODELS_DIR, RF_PROBABILITY_THRESHOLD, RF_LOOKAHEAD_TARGET

def create_labels(df: pd.DataFrame, target_period: int = RF_LOOKAHEAD_TARGET, atr_sl_mult: float = 1.5, atr_tp_mult: float = 3.0) -> pd.DataFrame:
    """Creates binary labels (1=Success, 0=Fail) without Lookahead Bias during training."""
    df = df.copy()

    # We define Success if the price hits TP before SL within the next `target_period` bars.
    # To do this correctly:
    # 1. We look ahead `target_period` bars from the current row.
    # 2. We calculate the max high and min low in that window.
    # 3. If max high > current close + (ATR * tp_mult) and min low > current close - (ATR * sl_mult) => Long Success (1)

    df['Target_High'] = df['High'].rolling(target_period).max().shift(-target_period)
    df['Target_Low'] = df['Low'].rolling(target_period).min().shift(-target_period)

    # Calculate SL and TP levels based on the shifted ATR (from features.py)
    # We assume 'ATRr_14' is the shifted ATR column name from pandas_ta
    atr_col = [c for c in df.columns if 'ATR' in c][0] if any('ATR' in c for c in df.columns) else None

    if not atr_col:
        log.warning("ATR column not found for ML labeling.")
        return df

    df['Long_TP'] = df['Close'] + (df[atr_col] * atr_tp_mult)
    df['Long_SL'] = df['Close'] - (df[atr_col] * atr_sl_mult)

    df['Short_TP'] = df['Close'] - (df[atr_col] * atr_tp_mult)
    df['Short_SL'] = df['Close'] + (df[atr_col] * atr_sl_mult)

    # Labeling Logic
    # 1 if Target_High hits TP and Target_Low doesn't hit SL (Simplified)
    df['Long_Success'] = np.where((df['Target_High'] >= df['Long_TP']) & (df['Target_Low'] > df['Long_SL']), 1, 0)
    df['Short_Success'] = np.where((df['Target_Low'] <= df['Short_TP']) & (df['Target_High'] < df['Short_SL']), 1, 0)

    # Drop rows where target window extends into the future (NaNs)
    df.dropna(subset=['Target_High', 'Target_Low'], inplace=True)
    return df

def train_model(ticker: str, df: pd.DataFrame, direction: str) -> bool:
    """Trains a RandomForestClassifier on historical data and saves the model."""
    df = create_labels(df)
    if df.empty:
        log.warning(f"Not enough data to train ML for {ticker}")
        return False

    # Features: Everything except price, volume, and targets
    exclude_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Target_High', 'Target_Low', 'Long_TP', 'Long_SL', 'Short_TP', 'Short_SL', 'Long_Success', 'Short_Success']
    feature_cols = [c for c in df.columns if c not in exclude_cols]

    if not feature_cols:
         log.warning("No features found for ML training.")
         return False

    X = df[feature_cols]
    y = df[f'{direction}_Success']

    # Simple RF Model - constrained to prevent overfitting
    model = RandomForestClassifier(n_estimators=100, max_depth=5, min_samples_split=10, random_state=42, n_jobs=-1)

    try:
        model.fit(X, y)
        model_path = os.path.join(MODELS_DIR, f"{ticker.replace('=','_')}_{direction}.pkl")
        joblib.dump(model, model_path)
        log.info(f"ML Model trained and saved for {ticker} {direction}. Accuracy on training: {model.score(X, y):.2f}")
        return True
    except Exception as e:
        log.error(f"Failed to train ML model for {ticker}: {e}")
        return False

def validate_signal(ticker: str, df: pd.DataFrame, direction: str) -> bool:
    """Predicts the probability of success using the trained RF model."""
    model_path = os.path.join(MODELS_DIR, f"{ticker.replace('=','_')}_{direction}.pkl")

    if not os.path.exists(model_path):
        log.warning(f"No ML model found for {ticker} {direction}. Training now...")
        train_model(ticker, df, direction)
        if not os.path.exists(model_path):
            return True # Fallback: Allow signal if ML fails to train

    model = joblib.load(model_path)

    exclude_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Target_High', 'Target_Low', 'Long_TP', 'Long_SL', 'Short_TP', 'Short_SL', 'Long_Success', 'Short_Success']
    feature_cols = [c for c in df.columns if c not in exclude_cols]

    latest_features = df[feature_cols].iloc[[-1]] # 2D array for predict

    try:
        # predict_proba returns [[P(Class 0), P(Class 1)]]
        prob_success = model.predict_proba(latest_features)[0][1]
        log.debug(f"ML Probability for {ticker} {direction}: {prob_success:.2f}")

        if prob_success >= RF_PROBABILITY_THRESHOLD:
            return True
        else:
            log.info(f"ML Veto: {ticker} {direction} probability {prob_success:.2f} < {RF_PROBABILITY_THRESHOLD}")
            return False

    except Exception as e:
        log.error(f"Failed to validate signal with ML for {ticker}: {e}")
        return True # Fallback: Allow signal if prediction fails

if __name__ == "__main__":
    from ed_quant_engine.data_loader import fetch_data
    from ed_quant_engine.features import add_features
    df = fetch_data("GC=F", "1d")
    df = add_features(df)
    train_model("GC=F", df, "Long")
    validate_signal("GC=F", df, "Long")
