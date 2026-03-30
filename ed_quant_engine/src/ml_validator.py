import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from .config import MODEL_DIR, ML_CONFIDENCE_THRESHOLD
from .logger import log_info, log_error, log_warning

def create_labels(df: pd.DataFrame, target_return: float = 0.02, stop_loss: float = 0.01, window: int = 10) -> pd.DataFrame:
    """
    Hedef Etiket (Label) oluşturur. Bir mum sonrasında fiyat, stop_loss'a çarpmadan
    target_return hedefine N mum (window) içinde ulaşmışsa başarılı (1), aksi halde (0).
    Lookahead Bias olmaması için geleceğe bakan '.shift(-n)' kullanılır.
    Bu veriler sadece EĞİTİM için kullanılır, SİNYAL ÜRETİMİNDE KULLANILMAZ.
    """
    df = df.copy()

    # İleriye dönük maksimum getiri ve maksimum düşüşü hesapla
    future_high = df['High'].rolling(window=window).max().shift(-window)
    future_low = df['Low'].rolling(window=window).min().shift(-window)

    # 1: Başarılı Trade (TP'ye değdi ve öncesinde SL'ye değmedi)
    # Basit bir simülasyon
    df['Label'] = np.where(
        (future_high > df['Close'] * (1 + target_return)) &
        (future_low > df['Close'] * (1 - stop_loss)),
        1, 0
    )

    # NaN olan son window kadar satırı sil (Geleceği bilemeyiz)
    df.dropna(subset=['Label'], inplace=True)
    return df

def train_and_save_model(ticker: str, df: pd.DataFrame):
    """
    Yerel (Local CPU) bir Makine Öğrenmesi (Random Forest) modeli eğitir ve
    modeller klasörüne kaydeder. Otonom olarak hafta sonları çalıştırılabilir.
    """
    log_info(f"[{ticker}] Makine Öğrenmesi Modeli Eğitiliyor...")

    # Özellikler (Features - X)
    features = [c for c in df.columns if 'HTF_' in c or c in ['RSI_14', 'MACD_12_26_9', 'Returns', 'BBL_20_2.0', 'BBU_20_2.0', 'ATRr_14']]

    df_labeled = create_labels(df)

    if len(df_labeled) < 500: # Veri yetersiz
        log_warning(f"[{ticker}] Yetersiz veri ({len(df_labeled)} satır), model eğitilmedi.")
        return

    X = df_labeled[features].dropna()
    y = df_labeled.loc[X.index, 'Label']

    # Train-Test Split (Sıralı olmalı, zaman serisi karıştırılamaz)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    accuracy = model.score(X_test, y_test)
    log_info(f"[{ticker}] Model Eğitildi. Doğruluk (Accuracy): {accuracy:.2f}")

    # Kaydet
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, os.path.join(MODEL_DIR, f"{ticker}_rf_model.pkl"))

def check_ml_veto(ticker: str, current_features: pd.Series) -> bool:
    """
    Sinyal geldiğinde, makine öğrenmesi modelinden tahmin alır.
    Eğer başarı ihtimali belirlenen eşiğin (örn %60) altındaysa sinyali reddeder (Veto).
    """
    model_path = os.path.join(MODEL_DIR, f"{ticker}_rf_model.pkl")
    if not os.path.exists(model_path):
        log_warning(f"[{ticker}] ML Modeli bulunamadı, Veto Atlandı.")
        return False

    model = joblib.load(model_path)

    # İlgili özellikleri seç
    feature_names = model.feature_names_in_
    try:
        X = current_features[feature_names].to_frame().T
        prob = model.predict_proba(X)[0][1] # Sınıf 1 (Başarı) ihtimali

        if prob < ML_CONFIDENCE_THRESHOLD:
            log_warning(f"🚨 ML VETOSU: [{ticker}] Başarı İhtimali %{prob*100:.1f} (Eşik: %{ML_CONFIDENCE_THRESHOLD*100}). Sinyal Reddedildi.")
            return True
        else:
            log_info(f"✅ ML ONAYI: [{ticker}] Başarı İhtimali %{prob*100:.1f} ile onaylandı.")
            return False
    except Exception as e:
        log_error(f"[{ticker}] ML Tahmin Hatası: {e}")
        return False
