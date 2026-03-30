import re

with open("ed_quant_engine/main.py", "r") as f:
    content = f.read()

# Fix retrain_ml_models to fetch both HTF and LTF and merge them properly for training.
old_retrain = """def retrain_ml_models():
    \"\"\"Haftalık (Pazar günleri) otonom makine öğrenmesi yeniden eğitimi.\"\"\"
    log_info("🤖 Haftalık ML Modelleri Yeniden Eğitiliyor...")
    from src.ml_validator import train_and_save_model
    tickers = get_all_tickers()
    for ticker in tickers:
        df = fetch_data_sync(ticker, period="5y", interval="1d")
        if df is not None:
            df = add_features(df, is_htf=True)
            train_and_save_model(ticker, df)
    log_info("🤖 ML Eğitim Süreci Tamamlandı.")"""

new_retrain = """def retrain_ml_models():
    \"\"\"Haftalık (Pazar günleri) otonom makine öğrenmesi yeniden eğitimi.\"\"\"
    log_info("🤖 Haftalık ML Modelleri Yeniden Eğitiliyor...")
    from src.ml_validator import train_and_save_model
    tickers = get_all_tickers()
    for ticker in tickers:
        df_htf = fetch_data_sync(ticker, period="2y", interval="1d")
        df_ltf = fetch_data_sync(ticker, period="60d", interval="1h")

        if df_htf is not None and df_ltf is not None:
            df_htf_feat = add_features(df_htf, is_htf=True)
            df_ltf_feat = add_features(df_ltf, is_htf=False)
            df_merged = merge_mtf_data(df_ltf_feat, df_htf_feat)
            train_and_save_model(ticker, df_merged)
    log_info("🤖 ML Eğitim Süreci Tamamlandı.")"""

content = content.replace(old_retrain, new_retrain)

with open("ed_quant_engine/main.py", "w") as f:
    f.write(content)
