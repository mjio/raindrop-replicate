"""Tests for replicate() orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from raindrop_replicate.replicate import replicate
from raindrop_replicate.storage import write_bookmark_file
from tests.conftest import bookmark_payload, patch_raindrop_client


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    pages: dict[int, list[dict[str, object]]],
) -> None:
    patch_raindrop_client(monkeypatch, pages)


def test_first_invocation_creates_all_eligible_bookmarks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {
        0: [
            bookmark_payload(1, created="2026-07-15T10:00:00Z"),
            bookmark_payload(2, created="2026-07-15T11:00:00Z"),
        ],
    }
    _patch_client(monkeypatch, pages)
    result = replicate(
        token="token",
        collection_id=1,
        directory=tmp_path,
        until=datetime(2026, 7, 15, 16, 0, tzinfo=UTC),
    )
    assert result.created == 2
    assert (tmp_path / "Bookmark 1.md").exists()
    assert (tmp_path / "Bookmark 2.md").exists()


def test_second_identical_invocation_creates_no_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {0: [bookmark_payload(1, created="2026-07-15T10:00:00Z")]}
    _patch_client(monkeypatch, pages)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    first = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    second = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert first.created == 1
    assert second.created == 0
    assert second.skipped == 1


def test_later_invocation_creates_only_new_ids(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages_first = {0: [bookmark_payload(1, created="2026-07-15T10:00:00Z")]}
    _patch_client(monkeypatch, pages_first)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)

    pages_second = {
        0: [
            bookmark_payload(1, created="2026-07-15T10:00:00Z"),
            bookmark_payload(2, created="2026-07-15T11:00:00Z"),
        ],
    }
    _patch_client(monkeypatch, pages_second)
    second = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert second.created == 1
    assert second.skipped == 1


def test_backdated_bookmark_discovered_later(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages_first = {0: [bookmark_payload(2, created="2026-07-15T11:00:00Z")]}
    _patch_client(monkeypatch, pages_first)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)

    pages_second = {
        0: [
            bookmark_payload(1, created="2026-07-15T09:00:00Z"),
            bookmark_payload(2, created="2026-07-15T11:00:00Z"),
        ],
    }
    _patch_client(monkeypatch, pages_second)
    second = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert second.created == 1
    assert (tmp_path / "Bookmark 1.md").exists()


def test_existing_update_does_not_rewrite_markdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {
        0: [
            bookmark_payload(
                1,
                title="Original",
                note="first",
                created="2026-07-15T10:00:00Z",
            )
        ],
    }
    _patch_client(monkeypatch, pages)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    original_content = (tmp_path / "Original.md").read_text(encoding="utf-8")

    pages_updated = {
        0: [
            bookmark_payload(
                1, title="Changed", note="updated", created="2026-07-15T10:00:00Z"
            )
        ],
    }
    _patch_client(monkeypatch, pages_updated)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert (tmp_path / "Original.md").read_text(encoding="utf-8") == original_content


def test_deleted_bookmark_does_not_delete_local_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {0: [bookmark_payload(1, created="2026-07-15T10:00:00Z")]}
    _patch_client(monkeypatch, pages)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert (tmp_path / "Bookmark 1.md").exists()

    _patch_client(monkeypatch, {0: []})
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert (tmp_path / "Bookmark 1.md").exists()


def test_missing_local_file_is_repaired(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {0: [bookmark_payload(1, created="2026-07-15T10:00:00Z")]}
    _patch_client(monkeypatch, pages)
    cutoff = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
    replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    (tmp_path / "Bookmark 1.md").unlink()

    second = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    assert second.repaired == 1
    assert (tmp_path / "Bookmark 1.md").exists()


def test_duplicate_titles_produce_numeric_suffixes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {
        0: [
            bookmark_payload(1, title="Same Title", created="2026-07-15T10:00:00Z"),
            bookmark_payload(2, title="Same Title", created="2026-07-15T10:01:00Z"),
        ],
    }
    _patch_client(monkeypatch, pages)
    result = replicate(
        token="token",
        collection_id=1,
        directory=tmp_path,
        until=datetime(2026, 7, 15, 16, 0, tzinfo=UTC),
    )
    assert result.created == 2
    assert (tmp_path / "Same Title.md").exists()
    assert (tmp_path / "Same Title (2).md").exists()


def test_identical_urls_different_ids_produce_separate_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pages = {
        0: [
            bookmark_payload(
                1,
                title="First",
                link="https://example.com/x",
                created="2026-07-15T10:00:00Z",
            ),
            bookmark_payload(
                2,
                title="Second",
                link="https://example.com/x",
                created="2026-07-15T10:01:00Z",
            ),
        ],
    }
    _patch_client(monkeypatch, pages)
    result = replicate(
        token="token",
        collection_id=1,
        directory=tmp_path,
        until=datetime(2026, 7, 15, 16, 0, tzinfo=UTC),
    )
    assert result.created == 2
    assert (tmp_path / "First.md").exists()
    assert (tmp_path / "Second.md").exists()


def test_end_to_end_offline_multi_page(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from raindrop_replicate.models import Bookmark

    bookmarks: list[dict[str, object]] = []
    for index in range(1, 56):
        bookmarks.append(
            bookmark_payload(
                index,
                title="Shared Title" if index in {10, 11} else f"Bookmark {index}",
                created=f"2026-07-15T{index // 60:02d}:{index % 60:02d}:00Z",
            )
        )
    bookmarks.append(bookmark_payload(999, created="2026-07-15T23:59:59Z"))

    pages = {
        0: bookmarks[0:50],
        1: bookmarks[50:56],
        2: bookmarks[56:57],
        3: [],
    }
    _patch_client(monkeypatch, pages)
    cutoff = datetime(2026, 7, 15, 22, 0, tzinfo=UTC)

    write_bookmark_file(
        tmp_path,
        "Bookmark 4.md",
        Bookmark(
            id=4,
            collection_id=1,
            title="Bookmark 4",
            link="https://example.com/4",
            excerpt="",
            note="",
            tags=(),
            created=datetime(2026, 7, 15, 0, 4, tzinfo=UTC),
            last_update=datetime(2026, 7, 15, 0, 4, tzinfo=UTC),
            type="article",
            important=False,
            highlights=(),
        ),
    )

    first = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)
    first_content = {
        path.name: path.read_text(encoding="utf-8") for path in tmp_path.glob("*.md")
    }

    pages_second = dict(pages)
    pages_second[0] = [
        bookmark_payload(1000, created="2026-07-15T08:00:00Z"),
        *pages[0],
    ]
    _patch_client(monkeypatch, pages_second)
    second = replicate(token="token", collection_id=1, directory=tmp_path, until=cutoff)

    second_content = {
        path.name: path.read_text(encoding="utf-8") for path in tmp_path.glob("*.md")
    }

    assert first.created + first.skipped + first.repaired > 0
    assert second.created == 1
    for name, content in first_content.items():
        assert second_content[name] == content
    assert (tmp_path / "Bookmark 1000.md").exists()
