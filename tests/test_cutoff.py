"""Tests for cutoff handling."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from raindrop_replicate.replicate import normalize_cutoff, replicate
from tests.conftest import bookmark_payload, patch_raindrop_client


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValueError, match="until must be timezone aware"):
        normalize_cutoff(datetime(2026, 7, 15))


def test_bookmark_exactly_at_cutoff_included(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    cutoff = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    pages = {
        0: [bookmark_payload(1, created="2026-07-15T12:00:00Z")],
    }
    patch_raindrop_client(monkeypatch, pages)
    result = replicate(
        token="token",
        collection_id=1,
        directory=tmp_path,
        until=cutoff,
    )
    assert result.created == 1


def test_bookmark_one_microsecond_after_cutoff_excluded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cutoff = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
    pages = {
        0: [bookmark_payload(1, created="2026-07-15T12:00:00.000001Z")],
    }
    patch_raindrop_client(monkeypatch, pages)
    result = replicate(
        token="token",
        collection_id=1,
        directory=tmp_path,
        until=cutoff,
    )
    assert result.created == 0
    assert result.excluded_after_cutoff == 1
