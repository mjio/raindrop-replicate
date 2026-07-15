"""Tests for JSON ledger."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from raindrop_replicate.exceptions import LedgerFormatError
from raindrop_replicate.ledger import LEDGER_FILENAME, Ledger
from raindrop_replicate.models import LedgerEntry


def test_missing_ledger_creates_empty_state(tmp_path: Path) -> None:
    ledger = Ledger.load(tmp_path)
    assert ledger.entries == {}


def test_valid_ledger_loading(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "entries": {
            "123456789": {
                "collection_id": 123456,
                "path": "Article About Agents.md",
                "created_at": "2026-07-15T12:30:00Z",
                "replicated_at": "2026-07-15T14:00:12Z",
            }
        },
    }
    (tmp_path / LEDGER_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    ledger = Ledger.load(tmp_path)
    entry = ledger.get(123456789)
    assert entry is not None
    assert entry.path == "Article About Agents.md"


def test_invalid_json(tmp_path: Path) -> None:
    (tmp_path / LEDGER_FILENAME).write_text("{bad", encoding="utf-8")
    with pytest.raises(LedgerFormatError, match="invalid JSON"):
        Ledger.load(tmp_path)


def test_unsupported_version(tmp_path: Path) -> None:
    payload = {"version": 2, "entries": {}}
    (tmp_path / LEDGER_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerFormatError, match="unsupported ledger version"):
        Ledger.load(tmp_path)


def test_invalid_bookmark_ids(tmp_path: Path) -> None:
    entry = {
        "collection_id": 1,
        "path": "a.md",
        "created_at": "2026-07-15T12:30:00Z",
        "replicated_at": "2026-07-15T14:00:12Z",
    }
    payload = {"version": 1, "entries": {"abc": entry}}
    (tmp_path / LEDGER_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerFormatError, match="invalid bookmark id"):
        Ledger.load(tmp_path)


def test_duplicate_paths(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "entries": {
            "1": {
                "collection_id": 1,
                "path": "Same.md",
                "created_at": "2026-07-15T12:30:00Z",
                "replicated_at": "2026-07-15T14:00:12Z",
            },
            "2": {
                "collection_id": 1,
                "path": "same.md",
                "created_at": "2026-07-15T12:30:00Z",
                "replicated_at": "2026-07-15T14:00:12Z",
            },
        },
    }
    (tmp_path / LEDGER_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(LedgerFormatError, match="duplicate ledger path"):
        Ledger.load(tmp_path)


def test_atomic_replacement(tmp_path: Path) -> None:
    ledger = Ledger({})
    ledger.add(
        1,
        LedgerEntry(
            collection_id=1,
            path="A.md",
            created_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
            replicated_at=datetime(2026, 7, 15, 14, 0, tzinfo=UTC),
        ),
    )
    ledger.save(tmp_path)
    saved = json.loads((tmp_path / LEDGER_FILENAME).read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert "1" in saved["entries"]
    assert not (tmp_path / f"{LEDGER_FILENAME}.tmp").exists()


def test_failed_temporary_write_leaves_previous_ledger_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = {"version": 1, "entries": {}}
    (tmp_path / LEDGER_FILENAME).write_text(json.dumps(original), encoding="utf-8")
    ledger = Ledger.load(tmp_path)

    def fail_fsync(fd: int) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.fsync", fail_fsync)
    with pytest.raises(OSError):
        ledger.save(tmp_path)

    saved = json.loads((tmp_path / LEDGER_FILENAME).read_text(encoding="utf-8"))
    assert saved == original
