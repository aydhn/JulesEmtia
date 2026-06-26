from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score

from src.config import MIN_RF_OOS_ACCURACY, MIN_RF_PROBABILITY, MIN_TRAINING_ROWS
from src.logger import get_logger
from src.paths import MODEL_DIR, model_file


logger = get_logger()
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Tickers that have been warned about insufficient data — only warn once per process.
_warned_sparse_tickers: set[str] = set()

FEATURE_CANDIDATES = [
    "RSI_14",
    "ATR_14",
    "Log_Ret",
    "MFI_14",
    "CMF_20",
    "ATR_PCT",
    "ATR_PCT_RANK_100",
    "VOL_REGIME",
    "Bull_Div",
    "Bear_Div",
    "MFI_Bull_Div",
    "MFI_Bear_Div",
    "MACD_Bull_Div",
    "MACD_Bear_Div",
    "Range_PCT",
    "Body_PCT",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_feature_list(df: pd.DataFrame) -> list[str]:
    features = [col for col in FEATURE_CANDIDATES if col in df.columns]
    for prefix in ("MACDh", "ADX_", "STOCHRSIk", "STOCHRSId", "SUPERTd_"):
        cols = [c for c in df.columns if c.startswith(prefix)]
        if cols:
            features.append(cols[0])
    seen: set[str] = set()
    return [f for f in features if not (f in seen or seen.add(f))]


def create_labels(
    df: pd.DataFrame,
    horizon: int = 5,
    tp_mult: float = 1.0,
    sl_mult: float = 0.5,
) -> pd.DataFrame:
    labels = np.zeros(len(df), dtype=int)
    for i in range(len(df) - horizon):
        entry_price = float(df["Close"].iloc[i])
        atr = float(df["ATR_14"].iloc[i]) if "ATR_14" in df.columns and not pd.isna(df["ATR_14"].iloc[i]) else entry_price * 0.01
        atr = atr if atr > 0 else entry_price * 0.01
        tp = entry_price + (atr * tp_mult)
        sl = entry_price - (atr * sl_mult)
        for j in range(1, horizon + 1):
            high = float(df["High"].iloc[i + j])
            low = float(df["Low"].iloc[i + j])
            if high >= tp:
                labels[i] = 1
                break
            if low <= sl:
                labels[i] = 0
                break
    out = df.copy()
    out["Target"] = labels
    return out.iloc[:-horizon].copy()


def _model_paths(ticker: str) -> tuple:
    pkl_path = model_file(ticker, "model.pkl")
    manifest_path = model_file(ticker, "model.json")
    return pkl_path, manifest_path


def train_symbol_model(ticker: str, historical_df: pd.DataFrame) -> tuple[bool, float]:
    if len(historical_df) < MIN_TRAINING_ROWS:
        if ticker not in _warned_sparse_tickers:
            logger.warning(
                "Not enough data to train RF for %s (%s rows). Will keep retrying silently.",
                ticker,
                len(historical_df),
            )
            _warned_sparse_tickers.add(ticker)
        else:
            logger.debug("RF skipped for %s: still sparse (%s rows).", ticker, len(historical_df))
        return False, 0.0

    features = _build_feature_list(historical_df)
    if len(features) < 5:
        logger.warning("Too few valid RF features for %s: %s", ticker, features)
        return False, 0.0

    try:
        df_labeled = create_labels(historical_df)
        df_labeled = df_labeled.replace([np.inf, -np.inf], np.nan).dropna(subset=features + ["Target"])
    except Exception as exc:
        logger.error("Label creation failed for %s: %s", ticker, exc)
        return False, 0.0

    if len(df_labeled) < 150 or df_labeled["Target"].nunique() < 2:
        logger.warning("RF training skipped for %s: insufficient labeled class diversity.", ticker)
        return False, 0.0

    split = int(len(df_labeled) * 0.75)
    train_df = df_labeled.iloc[:split]
    test_df = df_labeled.iloc[split:]
    if test_df.empty or test_df["Target"].nunique() < 2:
        logger.warning("RF training skipped for %s: OOS split lacks class diversity.", ticker)
        return False, 0.0

    X_train, y_train = train_df[features], train_df["Target"]
    X_test, y_test = test_df[features], test_df["Target"]

    try:
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=7,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        oos_accuracy = float(accuracy_score(y_test, predictions))
        oos_precision = float(precision_score(y_test, predictions, zero_division=0))

        payload = {"model": model, "features": features}
        manifest = {
            "ticker": ticker,
            "model_type": "RandomForestClassifier",
            "schema_version": 2,
            "trained_at": _utc_now(),
            "features": features,
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "oos_accuracy": oos_accuracy,
            "oos_precision": oos_precision,
            "min_oos_accuracy": MIN_RF_OOS_ACCURACY,
        }
        pkl_path, manifest_path = _model_paths(ticker)
        joblib.dump(payload, pkl_path)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info(
            "RF model saved for %s. OOS accuracy=%.2f%% precision=%.2f%% features=%s",
            ticker,
            oos_accuracy * 100,
            oos_precision * 100,
            features,
        )
        return oos_accuracy >= MIN_RF_OOS_ACCURACY, oos_accuracy * 100
    except Exception as exc:
        logger.error("RF training error for %s: %s", ticker, exc, exc_info=True)
        return False, 0.0


def _load_manifest(ticker: str) -> dict[str, Any] | None:
    _, manifest_path = _model_paths(ticker)
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def validate_signal(ticker: str, current_features, threshold: float = MIN_RF_PROBABILITY) -> bool:
    pkl_path, _ = _model_paths(ticker)
    manifest = _load_manifest(ticker)
    if not pkl_path.exists() or not manifest:
        logger.info("RF deferred [%s]: model or manifest missing.", ticker)
        return False
    if float(manifest.get("oos_accuracy", 0.0)) < MIN_RF_OOS_ACCURACY:
        logger.info(
            "RF veto [%s]: OOS accuracy %.3f < %.3f",
            ticker,
            float(manifest.get("oos_accuracy", 0.0)),
            MIN_RF_OOS_ACCURACY,
        )
        return False

    try:
        payload = joblib.load(pkl_path)
        model: RandomForestClassifier = payload["model"]
        features: list[str] = payload["features"]
        if features != manifest.get("features"):
            logger.info("RF veto [%s]: feature manifest mismatch.", ticker)
            return False

        input_vec = []
        for feature in features:
            if isinstance(current_features, pd.Series):
                value = current_features.get(feature, 0.0)
            elif isinstance(current_features, dict):
                value = current_features.get(feature, 0.0)
            else:
                value = 0.0
            input_vec.append(float(value) if not pd.isna(value) else 0.0)

        prob = float(model.predict_proba(np.array(input_vec).reshape(1, -1))[0][1])
        if prob >= threshold:
            return True
        logger.info("RF veto [%s]: P(success)=%.3f < threshold=%.2f", ticker, prob, threshold)
        return False
    except Exception as exc:
        logger.error("Error in RF validation for %s: %s", ticker, exc)
        return False


def train_model(combined_df: pd.DataFrame):
    logger.info("train_model() called; per-symbol training is handled by ContinuousLearner.")
