import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "DUMMY_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "123456789")
DB_PATH = "paper_db.sqlite3"
MODEL_PATH = "models/rf_model.pkl"