import requests
import time
from core.config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from core.logger import get_logger
from core.telegram_notifier import send_message
from db.paper_broker import PaperBroker
from main import app_state, run_live_cycle

log = get_logger()
broker = PaperBroker()

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {'timeout': 100, 'offset': offset}
    try:
        r = requests.get(url, params=params, timeout=105)
        return r.json()
    except Exception as e:
        log.error(f"Telegram Polling Error: {e}")
        return None

def handle_message(message):
    chat_id = str(message['chat']['id'])
    text = message.get('text', '')

    if chat_id != ADMIN_CHAT_ID:
        log.critical(f"Yetkisiz Erişim Denemesi: {chat_id}")
        return

    if text == '/durum':
        bal = broker.get_account_balance()
        pos = broker.get_open_positions()
        send_message(f"Kasa: ${bal:.2f}\nAçık Pozisyonlar: {len(pos)}")
    elif text == '/durdur':
        app_state['paused'] = True
        send_message("Sistem durduruldu. Sadece açık pozisyonlar takip ediliyor.")
    elif text == '/devam':
        app_state['paused'] = False
        send_message("Sistem tarama moduna geri döndü.")
    elif text == '/kapat_hepsi':
        pos = broker.get_open_positions()
        for p in pos:
            broker.close_position(p['trade_id'], p['entry_price'], 0, 'Panik Kapatması')
        send_message("Panik Kapatması Yapıldı. Tüm açık pozisyonlar kapatıldı.")
    elif text == '/tara':
        send_message("Manuel tarama başlatıldı.")
        run_live_cycle()
        send_message("Manuel tarama tamamlandı.")

def start_polling():
    offset = None
    while True:
        updates = get_updates(offset)
        if updates and updates.get('ok'):
            for update in updates['result']:
                offset = update['update_id'] + 1
                if 'message' in update:
                    handle_message(update['message'])
        time.sleep(1)

if __name__ == "__main__":
    start_polling()
