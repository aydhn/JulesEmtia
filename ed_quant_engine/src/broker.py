from abc import ABC, abstractmethod
from typing import Dict, List, Any
import paper_db
from .logger import log_info, log_error, log_warning
from datetime import datetime

class BaseBroker(ABC):
    """
    ED Capital Broker Soyutlama Katmanı (Interface).
    Tüm borsa bağlantıları (Paper, Binance, IBKR) bu standart şablonu miras alır.
    """
    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def get_open_positions(self) -> List[dict]:
        pass

    @abstractmethod
    def place_market_order(self, ticker: str, direction: str, qty: float, current_price: float, sl: float, tp: float, slippage: float, spread: float) -> str:
        pass

    @abstractmethod
    def modify_trailing_stop(self, trade_id: str, new_sl: float) -> bool:
        pass

    @abstractmethod
    def close_position(self, trade_id: str, close_price: float, reason: str) -> dict:
        pass

class PaperBroker(BaseBroker):
    """
    Yerel SQLite veritabanı (paper_db) ile gerçek dünyayı simüle eden Sanal Broker.
    SPL Düzey 3 (Türev) uyumlu 'Emir İletim Fişi' (Audit Trail) bırakır.
    """
    def __init__(self):
        # Eğer paper_db tablosu yoksa başlat
        paper_db.init_db()
        log_info("✅ PaperBroker (Sanal Broker) Başarıyla Bağlandı.")

    def get_account_balance(self) -> float:
        return paper_db.get_account_balance()

    def get_open_positions(self) -> List[dict]:
        return paper_db.get_open_trades()

    def place_market_order(self, ticker: str, direction: str, qty: float, current_price: float, sl: float, tp: float, slippage: float, spread: float) -> str:
        """
        Giriş Maliyetli Emir İletimi. Market fiyatına kayma ve spread eklendiği varsayılarak
        girilen fiyatlar (current_price) zaten Execution Model'den çıkmış olmalıdır.
        """
        # SPL Düzey 3 Uyumlu Denetim İzi (Audit Trail) Loglaması
        audit_trail = {
            "Time": datetime.now().isoformat(),
            "Ticker": ticker,
            "Type": "MARKET",
            "Direction": direction,
            "Qty": qty,
            "ExecutedPrice": current_price,
            "Slippage_Abs": slippage,
            "Spread_Abs": spread,
            "SL": sl,
            "TP": tp
        }
        log_info(f"🧾 [AUDIT TRAIL] Emir İletim Fişi: {audit_trail}")

        # SQLite Veritabanına Yaz
        trade_id = paper_db.open_trade(ticker, direction, current_price, sl, tp, qty)
        return trade_id

    def modify_trailing_stop(self, trade_id: str, new_sl: float) -> bool:
        """
        Zarar kes seviyesini günceller (Sadece lehe hareket edebilir).
        """
        paper_db.update_sl_price(trade_id, new_sl)
        log_info(f"🔄 [BROKER] İşlem {trade_id[:8]} için SL {new_sl:.4f} olarak güncellendi.")
        return True

    def close_position(self, trade_id: str, close_price: float, reason: str) -> dict:
        """
        İşlemi kapatır ve Kar/Zararı (PnL) net olarak SQLite bakiyesine ekler.
        """
        # İşlem detayını bul
        trades = self.get_open_positions()
        trade = next((t for t in trades if t['trade_id'] == trade_id), None)

        if not trade:
            log_error(f"❌ Kapatılacak açık işlem ({trade_id}) bulunamadı!")
            return {}

        entry_price = trade['entry_price']
        qty = trade['position_size']
        direction = trade['direction']

        # Brüt PnL
        if direction == "Long":
            pnl = (close_price - entry_price) * qty
        else:
            pnl = (entry_price - close_price) * qty

        # SQLite'ı Güncelle
        paper_db.close_trade(trade_id, close_price, pnl)

        # Kapanış Fişi
        receipt = {
            "TradeID": trade_id,
            "ClosePrice": close_price,
            "Reason": reason,
            "NetPnL": pnl
        }
        log_info(f"💸 [BROKER] İşlem Kapandı ({reason}): {pnl:.2f}$ PnL (Fiyat: {close_price:.4f})")
        return receipt
