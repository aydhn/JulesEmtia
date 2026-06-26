# JulesEmtia Project Memory

## Current State

- Canonical runtime is `ed_quant_engine`.
- Root runtime folders were retired; data/logs/models/reports now belong under `ed_quant_engine`.
- Paper account policy is archive-and-reset. Active DB: `ed_quant_engine/data/paper_db.sqlite3`.
- Existing legacy PPO/RF model files without manifests were quarantined. New models must include JSON manifests.
- `TELEGRAM_BOT_TOKEN` and `ADMIN_CHAT_ID` are the canonical Telegram variables. `TELEGRAM_CHAT_ID` is accepted only as a compatibility alias.

## Important Fixes

- MTF merge now computes LTF features and shifts HTF features by one full daily bar before `merge_asof`.
- Optional indicator NaNs no longer wipe the full feature set; only required columns are used for final drop checks.
- RF validation is fail-closed. No model/manifest means the signal is deferred, not approved.
- PPO observation space is fixed to manifest-backed feature columns and incompatible zips are quarantined.
- Logger uses UTF-8 rotating files and avoids duplicate handlers.
- Healthcheck accepts Yahoo 429 as degraded-but-reachable connectivity.

## Validation Snapshot

- `compileall`: passing.
- `pytest ed_quant_engine/tests -q`: passing.
- `scripts/windows_healthcheck.py`: passing with Yahoo 429 degraded warning.
- `scripts/runtime_diagnostics.py`: clean active log after pre-soak archive.

## Next Improvement Backlog

- Add richer unit tests for DB epoch reset, correlation veto, RF manifest mismatch and MTF lookahead behavior.
- Add benchmark reporting for weekly USDTRY comparison.
- Add a controlled offline demo-trade mode that uses a temp DB only, never the production paper account.
- Tune PPO reward beyond raw directional return, for example drawdown-aware or Sharpe-like reward.
