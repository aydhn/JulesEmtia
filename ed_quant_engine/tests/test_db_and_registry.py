"""Tests for paper_db idempotent init and model_registry."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


def _patch_paths(tmp_path: Path, monkeypatch):
    """Redirect all runtime paths to a temp directory."""
    import src.paths as paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "MODEL_DIR", tmp_path / "models")
    monkeypatch.setattr(paths, "REPORT_DIR", tmp_path / "reports")
    monkeypatch.setattr(paths, "ARCHIVE_DIR", tmp_path / "data" / "archive")
    monkeypatch.setattr(paths, "MODEL_QUARANTINE_DIR", tmp_path / "models" / "quarantine")
    monkeypatch.setattr(paths, "PAPER_DB_PATH", tmp_path / "data" / "paper_db.sqlite3")
    monkeypatch.setattr(paths, "MARKET_DB_PATH", tmp_path / "data" / "market_data.sqlite3")
    monkeypatch.setattr(paths, "LOG_PATH", tmp_path / "logs" / "quant_engine.log")


# ── paper_db sentinel test ────────────────────────────────────────────────────

def test_init_db_idempotent(tmp_path, monkeypatch):
    """init_db() should only log once per process; calling it N times is safe."""
    _patch_paths(tmp_path, monkeypatch)

    import src.paper_db as db
    # Reset sentinel for a clean test
    monkeypatch.setattr(db, "_db_initialized", False)

    db.init_db()
    assert db._db_initialized is True

    # Second call should be a no-op (no exception, sentinel stays True)
    db.init_db()
    assert db._db_initialized is True


def test_get_balance_returns_initial(tmp_path, monkeypatch):
    """get_balance() should return INITIAL_BALANCE on a fresh DB."""
    _patch_paths(tmp_path, monkeypatch)

    import src.paper_db as db
    from src.config import INITIAL_BALANCE

    monkeypatch.setattr(db, "_db_initialized", False)
    assert abs(db.get_balance() - INITIAL_BALANCE) < 0.01


# ── model_registry test ───────────────────────────────────────────────────────

def test_model_registry_record_and_history(tmp_path, monkeypatch):
    """record_training() persists and get_history() retrieves records."""
    import src.model_registry as reg

    monkeypatch.setattr(reg, "REGISTRY_DB_PATH", tmp_path / "model_registry.sqlite3")
    # Reinitialise schema in the temp path
    reg._init_registry()

    row_id = reg.record_training("GC=F", "RF", cycle=1, oos_accuracy=55.0, samples=600)
    assert row_id >= 1

    history = reg.get_history("GC=F", "RF")
    assert len(history) == 1
    assert history[0]["ticker"] == "GC=F"
    assert abs(history[0]["oos_accuracy"] - 55.0) < 0.01


def test_model_registry_not_degraded_without_history(tmp_path, monkeypatch):
    """is_degraded() returns False when fewer than MIN_HISTORY_CYCLES records exist."""
    import src.model_registry as reg

    monkeypatch.setattr(reg, "REGISTRY_DB_PATH", tmp_path / "model_registry.sqlite3")
    reg._init_registry()

    # Only 2 records — not enough for degradation detection
    reg.record_training("CL=F", "RF", cycle=1, oos_accuracy=60.0, samples=700)
    reg.record_training("CL=F", "RF", cycle=2, oos_accuracy=58.0, samples=700)

    assert reg.is_degraded("CL=F", "RF") is False
