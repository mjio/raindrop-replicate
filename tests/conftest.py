"""Shared test fixtures."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from raindrop_replicate.client import RaindropClient as _original_raindrop_client
from raindrop_replicate.models import Bookmark, Highlight


@pytest.fixture
def sample_bookmark() -> Bookmark:
    return Bookmark(
        id=123456789,
        collection_id=123456,
        title="Understanding Agent Loops",
        link="https://example.com/article",
        excerpt="Article excerpt from Raindrop.",
        note="Personal note from Raindrop.",
        tags=("agents", "python"),
        created=datetime(2026, 7, 15, 12, 30, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 31, 4, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(
            Highlight(
                id="62388e9e48b63606f41e44a6",
                text="First highlighted passage.",
                note="Highlight note.",
                color="yellow",
                created=datetime(2026, 7, 15, 12, 32, tzinfo=UTC),
            ),
        ),
    )


def bookmark_payload(
    bookmark_id: int,
    *,
    title: str | None = None,
    created: str = "2026-07-15T12:00:00Z",
    collection_id: int = 123456,
    link: str | None = None,
    note: str = "",
    excerpt: str = "",
    tags: list[str] | None = None,
    highlights: list[dict[str, object]] | None = None,
    last_update: str | None = None,
) -> dict[str, object]:
    return {
        "_id": bookmark_id,
        "collection": {"$id": collection_id},
        "title": title or f"Bookmark {bookmark_id}",
        "link": link or f"https://example.com/{bookmark_id}",
        "created": created,
        "lastUpdate": last_update or created,
        "excerpt": excerpt,
        "note": note,
        "tags": tags or [],
        "type": "article",
        "important": False,
        "highlights": highlights or [],
    }


def make_mock_transport(
    pages: dict[int, list[dict[str, object]]],
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params["page"])
        items = pages.get(page, [])
        return httpx.Response(
            200,
            json={"result": True, "items": items},
            request=request,
        )

    return httpx.MockTransport(handler)


def patch_raindrop_client(
    monkeypatch: pytest.MonkeyPatch,
    pages: dict[int, list[dict[str, object]]],
) -> None:
    transport = make_mock_transport(pages)

    def factory(token: str) -> _original_raindrop_client:
        return _original_raindrop_client(token, transport=transport)

    monkeypatch.setattr("raindrop_replicate.client.RaindropClient", factory)
