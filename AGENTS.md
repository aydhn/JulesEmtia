# AGENTS.md

## Mission

Build and maintain JulesEmtia as a zero-budget, local, low-frequency paper trading bot for commodities and TRY FX. The bot must continuously learn from local market data, improve its RF/PPO models, and report signals and paper-trade outcomes through Telegram without sending real orders.

## Non-Negotiable Constraints

- No paid APIs, paid data vendors or paid infrastructure.
- No real order execution.
- No web scraping with Selenium, BeautifulSoup or browser automation.
- No Streamlit/Flask/Dash dashboard.
- Runtime artifacts stay out of Git.
- Work on `master`; handoff requires `master == origin/master`.

## Engineering Rules

- Read code, logs and DB state before changing behavior.
- Read logs newest-to-oldest during incident work.
- Use `ed_quant_engine` as the only canonical app root.
- Keep `.env` at repo root; use `TELEGRAM_BOT_TOKEN` and `ADMIN_CHAT_ID`.
- Preserve lookahead protection: LTF signals may only use shifted closed HTF data.
- Keep RF/PPO model manifests in sync with feature columns and observation shape.
- Fail closed for ML/model uncertainty unless a test explicitly uses a temp demo mode.

## Validation Commands

```powershell
.\.venv\Scripts\python.exe -m compileall -q ed_quant_engine scripts
.\.venv\Scripts\python.exe -m pytest ed_quant_engine\tests -q
.\.venv\Scripts\python.exe scripts\windows_healthcheck.py
.\.venv\Scripts\python.exe scripts\runtime_diagnostics.py
```

## Runtime Proof

Use:

```powershell
$env:JULESEMTIA_AUTO_STOP_SECONDS=1800
$env:JULESEMTIA_NO_PAUSE=1
.\start_windows.bat
```

Acceptance requires 30 minutes of stable runtime and a clean diagnostic report after the run.
