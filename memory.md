# JulesEmtia Project Memory

## Güncel Durum (2026-06-27)

- Canonical runtime: `ed_quant_engine`.
- Runtime klasörleri: `data/`, `logs/`, `models/`, `reports/` — tümü `ed_quant_engine` altında.
- Paper account policy: archive-and-reset. Aktif DB: `ed_quant_engine/data/paper_db.sqlite3`.
- Model manifests zorunlu. Manifest yoksa veya uyumsuzsa → quarantine, sessiz onay yok.
- Model performans geçmişi: `ed_quant_engine/data/model_registry.sqlite3` (yeni).
- Telegram değişkenleri: `TELEGRAM_BOT_TOKEN` ve `ADMIN_CHAT_ID` canonical. `TELEGRAM_CHAT_ID` backward-compat alias.

## Kritik Düzeltmeler (Bu Oturum)

- `paper_db.py`: `_db_initialized` sentinel ile `init_db()` artık sadece bir kez çalışıyor.
  Log patlaması (27.000+ satır) bu değişiklikle giderildi.
- `logger.py`: `StreamHandler` seviyesi WARNING'e çekildi. Konsol artık yalnızca WARNING+
  mesajlarını gösteriyor. Log dosyası INFO seviyesinde yazmaya devam ediyor.
  Debug console: `JULESEMTIA_DEBUG_CONSOLE=1` env değişkeniyle açılır.
- `execution.py`: Kendi logger'ı yerine merkezi `get_logger()` kullanıyor.
- `ml_validator.py`: Sparse sembol tek-uyarı cache (`_warned_sparse_tickers`).
  GC=F, SI=F, PL=F gibi sembollerin tekrar eden WARNING'leri susturuldu.
- `reporter.py`: CRLF→LF, `INITIAL_BALANCE` config'den geliyor, f-string logger'lar temizlendi.
- `monte_carlo.py`: Ruin threshold config'den (`INITIAL_BALANCE * 0.5`), `numpy.random.default_rng()`.
- `continuous_learner.py`: TradingEnv Sharpe-like reward (Sharpe ratio ağırlıklı step reward).
  PPO model loaded mesajı DEBUG seviyesine düşürüldü.
- `walk_forward.py`: Gerçek entegrasyon, `INITIAL_BALANCE` config'den, WFE/robustness threshold.
- `model_registry.py`: YENİ — Her RF/PPO eğitiminin metriklerini SQLite'a kaydeder.
  `is_degraded()` ile otomatik re-bootstrap tetikleme.
- `.gitignore`: `quarantine/`, `.mypy_cache/`, `.agents/`, `.gemini/` eklendi.

## Mimari Kurallar

- Log seviyesi politikası: **Konsol=WARNING+**, **Dosya=INFO+**.
- Her model eğitimi `model_registry.record_training()` ile kaydedilmeli.
- RF ve PPO model manifestleri şema version 2 gerektirir.
- Lookahead koruması: LTF sinyalleri yalnızca shift edilmiş kapanmış HTF datasını kullanır.
- `init_db()` her yerden güvenle çağrılabilir — sentinel guard ile idempotent.

## Doğrulama Anlık Görüntüsü

- `compileall`: geçiyor.
- `pytest ed_quant_engine/tests -q`: geçiyor.
- `scripts/windows_healthcheck.py`: geçiyor.
- Konsol spam: giderildi (`paper_db.py` sentinel + logger WARNING seviyesi).

## Backlog

- Test kapsamı artırılacak: DB epoch reset, correlation veto, RF manifest mismatch, MTF lookahead.
- `model_registry.py` degradation detection'ı `send_training_report()`'a entegre et.
- USDTRY benchmark karşılaştırması haftalık rapora eklenecek.
- Kontrollü offline demo-trade modu (geçici DB, production account dokunulmaz).
- PPO adaptif timestep: win_rate >= 70% ise routine, < 50% ise bootstrap süresini 2x uzat.
- Walk-forward sonuçlarını `model_registry`'e kaydet (şu an `continuous_learner`'a bağlı değil).
