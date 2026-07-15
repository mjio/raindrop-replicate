"""Tests for domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from raindrop_replicate.exceptions import (
    AuthenticationError,
    LedgerFormatError,
    RaindropAPIError,
    RaindropReplicateError,
    RaindropResponseError,
    StorageConsistencyError,
)
from raindrop_replicate.models import (
    Bookmark,
    Highlight,
    LedgerEntry,
    ReplicationResult,
)


def _bookmark(**overrides: object) -> Bookmark:
    defaults = {
        "id": 123,
        "collection_id": 456,
        "title": "Test",
        "link": "https://example.com",
        "excerpt": "Excerpt",
        "note": "Note",
        "tags": ("python",),
        "created": datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        "last_update": datetime(2026, 7, 15, 12, 1, tzinfo=UTC),
        "type": "article",
        "important": False,
        "highlights": (),
    }
    defaults.update(overrides)
    return Bookmark(**defaults)  # type: ignore[arg-type]


def test_models_are_immutable() -> None:
    bookmark = _bookmark()
    with pytest.raises(ValidationError):
        bookmark.title = "Changed"  # type: ignore[misc]

    highlight = Highlight(
        id="abc",
        text="text",
        note=None,
        color=None,
        created=None,
    )
    with pytest.raises(ValidationError):
        highlight.text = "changed"  # type: ignore[misc]


def test_bookmark_ids_are_integers() -> None:
    bookmark = _bookmark(id=999, collection_id=111)
    assert isinstance(bookmark.id, int)
    assert isinstance(bookmark.collection_id, int)


def test_timestamps_are_timezone_aware() -> None:
    bookmark = _bookmark()
    assert bookmark.created.tzinfo is not None
    assert bookmark.last_update.tzinfo is not None

    naive = datetime(2026, 7, 15, 12, 0)
    with pytest.raises(ValidationError):
        _bookmark(created=naive)


def test_replication_result_fields() -> None:
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    result = ReplicationResult(
        collection_id=123,
        cutoff=cutoff,
        scanned=10,
        created=3,
        skipped=5,
        repaired=1,
        excluded_after_cutoff=1,
        files_created=(),
    )
    assert result.scanned == 10
    assert result.created == 3
    assert result.skipped == 5
    assert result.repaired == 1
    assert result.excluded_after_cutoff == 1


def test_ledger_entry() -> None:
    now = datetime(2026, 7, 15, 14, 0, 12, tzinfo=UTC)
    created = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)
    entry = LedgerEntry(
        collection_id=123456,
        path="Article About Agents.md",
        created_at=created,
        replicated_at=now,
    )
    assert entry.path == "Article About Agents.md"
    assert entry.created_at.tzinfo is not None
    assert entry.replicated_at.tzinfo is not None


def test_exception_hierarchy() -> None:
    assert issubclass(AuthenticationError, RaindropReplicateError)
    assert issubclass(RaindropAPIError, RaindropReplicateError)
    assert issubclass(RaindropResponseError, RaindropReplicateError)
    assert issubclass(LedgerFormatError, RaindropReplicateError)
    assert issubclass(StorageConsistencyError, RaindropReplicateError)
