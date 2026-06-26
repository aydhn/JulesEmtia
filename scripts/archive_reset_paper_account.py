from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "ed_quant_engine"
sys.path.insert(0, str(ENGINE_ROOT))

import src.paper_db as db


if __name__ == "__main__":
    result = db.archive_and_reset_account("manual_plan_archive_reset")
    print(result)
