import sqlite3
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

from core.logger import logger
from core.database import execute_query, fetch_query, fetch_dataframe

class BaseBroker:
    """Borsa işlemlerini soyutlayan SPL Düzey 3 arayüz."""
    pass

class PaperBroker(BaseBroker):
    """
    ED Capital kurumsal SQLite veritabanı (paper_db.sqlite3) üzerinde çalışan sanal aracı kurum.
    Gerçek dünya slippage/spread hesaplamalarını barındırır ve loglar (Audit Trail).
    """

    def __init__(self, initial_capital: float = 10000.0):
        self._initial_capital = initial_capital
        logger.info(f"Paper Broker başlatıldı. Başlangıç Kasası: {self._initial_capital} USD")

    def get_account_balance(self) -> float:
        """
        Gerçekleşmiş (Kapanmış) işlemlerin net kâr/zararı üzerinden güncel kasayı hesaplar.
        """
        query = "SELECT SUM(pnl) FROM trades WHERE status = 'Closed'"
        result = fetch_query(query)
        total_pnl = result[0][0] if result and result[0][0] is not None else 0.0
        current_balance = self._initial_capital + total_pnl
        return current_balance

    def place_market_order(self, ticker: str, direction: str, size: float, entry_price: float, sl: float, tp: float, fees: float) -> Dict[str, Any]:
        """
        Yeni bir sinyali veritabanına Açık (Open) işlem olarak yazar.
        Fees (Spread + Slippage) buraya dahil edilmiştir.
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            query = """
                INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, fees)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?)
            """
            params = (ticker, direction, now, entry_price, sl, tp, size, fees)
            execute_query(query, params)

            receipt = {
                "timestamp": now,
                "ticker": ticker,
                "direction": direction,
                "entry_price": entry_price,
                "size": size,
                "sl": sl,
                "tp": tp,
                "fees": fees,
                "status": "Success"
            }
            logger.info(f"Emir İletim Fişi (Audit Trail): {receipt}")
            return receipt
        except Exception as e:
            logger.error(f"PaperBroker place_market_order hatası: {e}")
            return {"status": "Failed", "error": str(e)}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Açık pozisyonları sözlük (dictionary) listesi olarak döndürür."""
        query = "SELECT trade_id, ticker, direction, entry_price, sl_price, tp_price, position_size, fees FROM trades WHERE status = 'Open'"
        results = fetch_query(query)

        open_positions = []
        for row in results:
            pos = {
                "trade_id": row[0],
                "ticker": row[1],
                "direction": row[2],
                "entry_price": row[3],
                "sl_price": row[4],
                "tp_price": row[5],
                "position_size": row[6],
                "fees": row[7]
            }
            open_positions.append(pos)
        return open_positions

    def get_open_positions_df(self) -> pd.DataFrame:
        query = "SELECT * FROM trades WHERE status = 'Open'"
        return fetch_dataframe(query)

    def modify_trailing_stop(self, trade_id: int, new_sl: float) -> None:
        """Veritabanındaki SL seviyesini dinamik kâr koruması için günceller."""
        query = "UPDATE trades SET sl_price = ? WHERE trade_id = ? AND status = 'Open'"
        execute_query(query, (new_sl, trade_id))
        logger.info(f"Trailing Stop Güncellendi - İşlem ID: {trade_id}, Yeni SL: {new_sl:.4f}")

    def close_position(self, trade_id: int, exit_price: float, pnl: float) -> None:
        """Bir işlemi piyasa emri ile (veya TP/SL tetiklenmesi ile) kapatır."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = "UPDATE trades SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ? WHERE trade_id = ? AND status = 'Open'"
        execute_query(query, (now, exit_price, pnl, trade_id))
        logger.info(f"Pozisyon Kapatıldı - İşlem ID: {trade_id}, Çıkış Fiyatı: {exit_price:.4f}, Net PNL: {pnl:.2f}")

    def panic_close_all(self, current_prices: Dict[str, float]) -> None:
        """
        Tüm açık pozisyonları o anki piyasa fiyatından zararına veya kârına derhal kapatır.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            logger.info("Panik Kapatması iptal edildi: Açık pozisyon bulunamadı.")
            return

        for pos in open_positions:
            ticker = pos["ticker"]
            direction = pos["direction"]
            entry_price = pos["entry_price"]
            size = pos["position_size"]
            fees = pos["fees"]

            exit_price = current_prices.get(ticker, entry_price)

            if direction == "Long":
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size

            net_pnl = pnl - (fees * 2)
            self.close_position(trade_id=pos["trade_id"], exit_price=exit_price, pnl=net_pnl)

        logger.critical(f"TÜM POZİSYONLAR KAPATILDI. Kapanan pozisyon sayısı: {len(open_positions)}")

    def panic_close_ticker(self, ticker: str, current_price: float) -> None:
        """
        Sadece belirli bir tickera ait (Örn: Flaş çöküş yiyen) açık pozisyonu derhal kapatır.
        """
        open_positions = self.get_open_positions()
        target_positions = [p for p in open_positions if p["ticker"] == ticker]

        if not target_positions:
            return

        for pos in target_positions:
            direction = pos["direction"]
            entry_price = pos["entry_price"]
            size = pos["position_size"]
            fees = pos["fees"]

            if direction == "Long":
                pnl = (current_price - entry_price) * size
            else:
                pnl = (entry_price - current_price) * size

            net_pnl = pnl - (fees * 2)
            self.close_position(trade_id=pos["trade_id"], exit_price=current_price, pnl=net_pnl)

        logger.critical(f"SPESİFİK PANİK KAPATMASI: {ticker} pozisyonu başarıyla kapatıldı.")