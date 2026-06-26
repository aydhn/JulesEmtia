# AI Engineering Notes

## Hard Constraints

- Zero paid APIs or paid data providers.
- No real broker orders; this is a paper trading and signal bot.
- No UI/dashboard. Telegram is the only user interface.
- No HTML scraping, Selenium or BeautifulSoup data pipelines.
- Keep runtime paths under `ed_quant_engine`.
- Use `master` and finish with `master == origin/master`.

## Architecture Rules

- Entrypoint: `start_windows.bat -> ed_quant_engine/main.py`.
- Scheduling is pure asyncio. Do not reintroduce `schedule`.
- `.env` lives at repo root and is loaded through `src.paths.ENV_PATH`.
- Runtime artifacts live under `ed_quant_engine/data`, `logs`, `models`, `reports`.
- Paper DB must stay schema-versioned and auditable through `src.paper_db.audit_trade_history()`.
- RF and PPO models require manifest files. Missing or mismatched manifests mean deferred/quarantined, not silent approval.
- Strategy must use closed-candle confirmation and shifted HTF data.

## Validation Before Handoff

```powershell
.\.venv\Scripts\python.exe -m compileall -q ed_quant_engine scripts
.\.venv\Scripts\python.exe -m pytest ed_quant_engine\tests -q
.\.venv\Scripts\python.exe scripts\windows_healthcheck.py
.\.venv\Scripts\python.exe scripts\runtime_diagnostics.py
```

For runtime proof, run `start_windows.bat` with a timed auto-stop:

```powershell
$env:JULESEMTIA_AUTO_STOP_SECONDS=1800
$env:JULESEMTIA_NO_PAUSE=1
.\start_windows.bat
```
