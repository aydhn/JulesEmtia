from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "ed_quant_engine"
sys.path.insert(0, str(ENGINE_ROOT))

import src.paper_db as db
from src.paths import LOG_PATH, MODEL_DIR


ERROR_MARKERS = ("ERROR", "CRITICAL", "Traceback", "PPO training failed", "Observation spaces do not match")


def scan_log_from_tail(limit: int = 20000) -> dict:
    if not LOG_PATH.exists():
        return {"log_path": str(LOG_PATH), "exists": False, "findings": []}
    lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = []
    for line in reversed(lines[-limit:]):
        if any(marker in line for marker in ERROR_MARKERS):
            findings.append(line)
        if len(findings) >= 30:
            break
    return {"log_path": str(LOG_PATH), "exists": True, "scanned_lines": min(limit, len(lines)), "findings": findings}


def model_manifest_summary() -> dict:
    rf_manifests = list(MODEL_DIR.glob("*_model.json"))
    ppo_manifests = list(MODEL_DIR.glob("*_ppo.json"))
    quarantine_dir = MODEL_DIR / "quarantine"
    quarantined = [path for path in quarantine_dir.rglob("*") if path.is_file()] if quarantine_dir.exists() else []
    return {
        "model_dir": str(MODEL_DIR),
        "rf_manifests": len(rf_manifests),
        "ppo_manifests": len(ppo_manifests),
        "quarantined_files": len(quarantined),
    }


if __name__ == "__main__":
    payload = {
        "trade_audit": db.audit_trade_history(),
        "log_scan": scan_log_from_tail(),
        "models": model_manifest_summary(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
