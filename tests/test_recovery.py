"""Tests for atomic storage and crash recovery."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from raindrop_replicate.exceptions import StorageConsistencyError
from raindrop_replicate.ledger import Ledger
from raindrop_replicate.markdown import render_markdown
from raindrop_replicate.models import Bookmark, LedgerEntry
from raindrop_replicate.storage import (
    atomic_write_text,
    read_raindrop_id,
    recover_ledger,
    scan_front_matter,
    write_bookmark_file,
)


def _bookmark(bookmark_id: int = 123, title: str = "Test Bookmark") -> Bookmark:
    return Bookmark(
        id=bookmark_id,
        collection_id=456,
        title=title,
        link="https://example.com",
        excerpt="Excerpt",
        note="Note",
        tags=(),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(),
    )


def test_file_created_before_ledger_update(tmp_path: Path) -> None:
    bookmark = _bookmark()
    path = write_bookmark_file(tmp_path, "Test Bookmark.md", bookmark)
    assert path.exists()
    assert not (tmp_path / ".raindrop-replicate.json").exists()


def test_recovery_after_crash_between_file_and_ledger(tmp_path: Path) -> None:
    bookmark = _bookmark()
    write_bookmark_file(tmp_path, "Test Bookmark.md", bookmark)
    ledger = Ledger.load(tmp_path)
    recovered = recover_ledger(tmp_path, ledger)
    assert recovered.contains(123)
    assert recovered.get(123).path == "Test Bookmark.md"


def test_duplicate_raindrop_ids_across_files(tmp_path: Path) -> None:
    bookmark = _bookmark()
    write_bookmark_file(tmp_path, "One.md", bookmark)
    write_bookmark_file(tmp_path, "Two.md", bookmark)
    with pytest.raises(StorageConsistencyError, match="duplicate raindrop_id"):
        scan_front_matter(tmp_path)


def test_ledger_and_front_matter_disagreement(tmp_path: Path) -> None:
    bookmark = _bookmark()
    write_bookmark_file(tmp_path, "Actual.md", bookmark)
    ledger = Ledger(
        {
            "123": LedgerEntry(
                collection_id=456,
                path="Wrong.md",
                created_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
                replicated_at=datetime(2026, 7, 15, 14, 0, tzinfo=UTC),
            )
        }
    )
    with pytest.raises(StorageConsistencyError):
        recover_ledger(tmp_path, ledger)


def test_missing_file_repair_path_exists(tmp_path: Path) -> None:
    bookmark = _bookmark()
    content = render_markdown(bookmark)
    atomic_write_text(tmp_path / "Missing.md", content)
    assert read_raindrop_id(tmp_path / "Missing.md") == 123


def test_untracked_markdown_files_preserved(tmp_path: Path) -> None:
    untracked = tmp_path / "manual.md"
    untracked.write_text("# Manual\n", encoding="utf-8")
    ledger = Ledger.load(tmp_path)
    recovered = recover_ledger(tmp_path, ledger)
    assert untracked.exists()
    assert not recovered.contains(123)
