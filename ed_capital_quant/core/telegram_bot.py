import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import io

from core.logger import logger
from core.database import fetch_dataframe
from analysis.reporter import PerformanceReporter

class TelegramInterface:
    """Çift Yönlü Telegram İletişim, Komut ve Raporlama Altyapısı."""

    def __init__(self, bot_token: str, admin_chat_id: str):
        self.bot_token = bot_token
        self.admin_chat_id = str(admin_chat_id)
        self.application = Application.builder().token(self.bot_token).build()
        self.is_paused = False # /durdur komutu ile sistemi bekletmek için
        self.engine_callback = None # main.py'deki fonksiyonlara erişim

        # Komutları Tanımla
        self.application.add_handler(CommandHandler("durum", self.cmd_status))
        self.application.add_handler(CommandHandler("durdur", self.cmd_pause))
        self.application.add_handler(CommandHandler("devam", self.cmd_resume))
        self.application.add_handler(CommandHandler("kapat_hepsi", self.cmd_panic_close))
        self.application.add_handler(CommandHandler("tara", self.cmd_force_scan))
        self.application.add_handler(CommandHandler("rapor", self.cmd_report))

    def _is_admin(self, update: Update) -> bool:
        """Whitelist: Sadece ADMIN_CHAT_ID komut çalıştırabilir."""
        user_id = str(update.effective_user.id)
        if user_id != self.admin_chat_id:
            logger.critical(f"YETKİSİZ ERİŞİM DENEMESİ! Kullanıcı ID: {user_id}")
            return False
        return True

    async def send_message(self, text: str):
        """Asenkron Mesaj Gönderme (Rate Limit korumalı)."""
        if not self.bot_token or not self.admin_chat_id:
            logger.error("Telegram API bilgileri eksik, mesaj gönderilemedi.")
            return

        try:
            await self.application.bot.send_message(chat_id=self.admin_chat_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Telegram mesaj gönderme hatası: {e}")

    async def send_document(self, file_path: str):
        """Asenkron HTML/PDF Rapor Gönderme."""
        try:
            with open(file_path, 'rb') as f:
                await self.application.bot.send_document(chat_id=self.admin_chat_id, document=f)
        except Exception as e:
            logger.error(f"Telegram döküman gönderme hatası: {e}")

    # ---- KOMUTLAR ----
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return

        # O anki güncel kasa ve açık pozisyonlar
        df_open = fetch_dataframe("SELECT * FROM trades WHERE status = 'Open'")
        df_closed = fetch_dataframe("SELECT * FROM trades WHERE status = 'Closed'")

        total_pnl = df_closed['pnl'].sum() if not df_closed.empty else 0.0
        msg = f"📊 <b>ED Capital Sistem Durumu</b>\n\n"
        msg += f"Kapatılmış İşlem Sayısı: {len(df_closed)}\n"
        msg += f"Toplam Net PnL: <b>${total_pnl:.2f}</b>\n\n"

        if df_open.empty:
            msg += "Açık pozisyon bulunmamaktadır."
        else:
            msg += f"<b>Açık Pozisyonlar ({len(df_open)}):</b>\n"
            for _, row in df_open.iterrows():
                msg += f"• {row['ticker']} | {row['direction']} | Giriş: {row['entry_price']:.4f}\n"

        msg += f"\n<i>Tarama Durumu: {'DURDURULDU ⏸️' if self.is_paused else 'AKTİF ▶️'}</i>"
        await self.send_message(msg)

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return
        self.is_paused = True
        await self.send_message("⏸️ <b>SİSTEM DURDURULDU</b>\nYeni sinyal taraması askıya alındı. Açık pozisyonların TP/SL takibi devam ediyor.")
        logger.warning("Kullanıcı komutu ile sistem DURAKLATILDI.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return
        self.is_paused = False
        await self.send_message("▶️ <b>SİSTEM DEVAM EDİYOR</b>\nOtonom tarama modu tekrar aktifleştirildi.")
        logger.info("Kullanıcı komutu ile sistem TEKRAR BAŞLATILDI.")

    async def cmd_panic_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return
        await self.send_message("🚨 <b>PANİK KAPATMASI BAŞLATILDI</b>\nTüm açık pozisyonlar acilen piyasa fiyatından kapatılıyor...")
        if self.engine_callback:
            # Main engine'deki panic_close fonksiyonunu tetikle
            await self.engine_callback("panic_close")
        else:
            await self.send_message("Hata: Motor bağlantısı kurulamadı.")

    async def cmd_force_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return
        if self.is_paused:
            await self.send_message("⚠️ Sistem şu an duraklatılmış (Paused) durumda. Önce /devam yazın.")
            return

        await self.send_message("🔍 <b>ZORUNLU TARAMA BAŞLATILDI</b>\nEvren taranıyor, lütfen bekleyin...")
        if self.engine_callback:
            await self.engine_callback("force_scan")

    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_admin(update): return
        await self.send_message("📄 <b>Tear Sheet (Rapor) Oluşturuluyor...</b>")
        reporter = PerformanceReporter()
        report_path = reporter.generate_tear_sheet()
        await self.send_document(report_path)

    def start_listening(self):
        """Polling'i arkaplanda başlatır (Non-blocking asenkron başlatıcı gerektirir)"""
        logger.info("Telegram Dinleme Modülü Başlatıldı.")
        # self.application.run_polling() asenkron main_loop'ta await edilecek.