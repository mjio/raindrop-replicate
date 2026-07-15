"""Tests for Raindrop API client and response parsing."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from raindrop_replicate.client import (
    RaindropClient,
    parse_bookmark,
    parse_bookmarks_response,
    parse_timestamp,
)
from raindrop_replicate.exceptions import (
    AuthenticationError,
    RaindropAPIError,
    RaindropResponseError,
)

COMPLETE_BOOKMARK = {
    "_id": 123456789,
    "collection": {"$id": 123456},
    "title": "Understanding Agent Loops",
    "link": "https://example.com/article",
    "excerpt": "Article excerpt from Raindrop.",
    "note": "Personal note from Raindrop.",
    "tags": ["agents", "python"],
    "created": "2026-07-15T12:30:00.000Z",
    "lastUpdate": "2026-07-15T12:31:04.000Z",
    "type": "article",
    "important": False,
    "highlights": [
        {
            "_id": "62388e9e48b63606f41e44a6",
            "text": "First highlighted passage.",
            "note": "Highlight note.",
            "color": "yellow",
            "created": "2026-07-15T12:32:00.000Z",
        }
    ],
    "domain": "example.com",
    "cover": "https://example.com/cover.jpg",
}


class TestParsing:
    def test_complete_bookmark(self) -> None:
        bookmark = parse_bookmark(COMPLETE_BOOKMARK)
        assert bookmark.id == 123456789
        assert bookmark.collection_id == 123456
        assert bookmark.title == "Understanding Agent Loops"
        assert bookmark.link == "https://example.com/article"
        assert bookmark.excerpt == "Article excerpt from Raindrop."
        assert bookmark.note == "Personal note from Raindrop."
        assert bookmark.tags == ("agents", "python")
        assert bookmark.type == "article"
        assert bookmark.important is False
        assert len(bookmark.highlights) == 1
        assert bookmark.highlights[0].text == "First highlighted passage."

    def test_missing_optional_fields(self) -> None:
        minimal = {
            "_id": 1,
            "collection": {"$id": 2},
            "title": "Title",
            "link": "https://example.com",
            "created": "2026-07-15T12:30:00Z",
        }
        bookmark = parse_bookmark(minimal)
        assert bookmark.excerpt == ""
        assert bookmark.note == ""
        assert bookmark.tags == ()
        assert bookmark.type == ""
        assert bookmark.important is False
        assert bookmark.highlights == ()
        assert bookmark.last_update == bookmark.created

    def test_highlights(self) -> None:
        bookmark = parse_bookmark(COMPLETE_BOOKMARK)
        highlight = bookmark.highlights[0]
        assert highlight.id == "62388e9e48b63606f41e44a6"
        assert highlight.color == "yellow"
        assert highlight.note == "Highlight note."
        assert highlight.created is not None
        assert highlight.created.tzinfo is not None

    def test_invalid_timestamp(self) -> None:
        data = dict(COMPLETE_BOOKMARK)
        data["created"] = "not-a-date"
        with pytest.raises(RaindropResponseError, match="invalid timestamp"):
            parse_bookmark(data)

    def test_missing_required_fields(self) -> None:
        with pytest.raises(RaindropResponseError, match="_id"):
            parse_bookmark({})
        with pytest.raises(RaindropResponseError, match="collection"):
            parse_bookmark({"_id": 1})
        with pytest.raises(RaindropResponseError, match="collection.\\$id"):
            parse_bookmark({"_id": 1, "collection": {}})
        with pytest.raises(RaindropResponseError, match="link"):
            parse_bookmark({"_id": 1, "collection": {"$id": 2}, "title": "T"})
        with pytest.raises(RaindropResponseError, match="title"):
            parse_bookmark(
                {"_id": 1, "collection": {"$id": 2}, "link": "https://example.com"}
            )
        with pytest.raises(RaindropResponseError, match="created"):
            parse_bookmark(
                {
                    "_id": 1,
                    "collection": {"$id": 2},
                    "link": "https://example.com",
                    "title": "T",
                }
            )

    def test_undocumented_fields_ignored(self) -> None:
        bookmark = parse_bookmark(COMPLETE_BOOKMARK)
        assert not hasattr(bookmark, "domain")
        assert not hasattr(bookmark, "cover")

    def test_parse_bookmarks_response(self) -> None:
        payload = {"result": True, "items": [COMPLETE_BOOKMARK]}
        bookmarks = parse_bookmarks_response(payload)
        assert len(bookmarks) == 1

    def test_parse_bookmarks_response_errors(self) -> None:
        with pytest.raises(RaindropResponseError, match="result"):
            parse_bookmarks_response({"result": False, "items": []})
        with pytest.raises(RaindropResponseError, match="items"):
            parse_bookmarks_response({"result": True})

    def test_parse_timestamp(self) -> None:
        parsed = parse_timestamp("2026-07-15T12:30:00Z", "created")
        assert parsed == datetime(2026, 7, 15, 12, 30, tzinfo=UTC)


def _make_response(
    status: int,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        headers=headers or {},
        request=httpx.Request("GET", "https://api.raindrop.io/rest/v1/raindrops/1"),
    )


class TestRaindropClient:
    def test_bearer_token_sent(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers["Authorization"]
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("secret-token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert captured["authorization"] == "Bearer secret-token"

    def test_sort_created_sent(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["sort"] = request.url.params["sort"]
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert captured["sort"] == "created"

    def test_perpage_50_sent(self) -> None:
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["perpage"] = request.url.params["perpage"]
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert captured["perpage"] == "50"

    def test_page_numbering_starts_at_zero(self) -> None:
        pages: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            pages.append(request.url.params["page"])
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.get_bookmarks(collection_id=1, page=2)
        client.close()
        assert pages == ["0", "2"]

    def test_nested_matches_include_nested(self) -> None:
        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.url.params["nested"])
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0, nested=False)
        client.get_bookmarks(collection_id=1, page=0, nested=True)
        client.close()
        assert captured == ["false", "true"]

    def test_429_retried(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return _make_response(429, {"result": False})
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert attempts == 2

    def test_5xx_retried(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return _make_response(503, {"result": False})
            return _make_response(200, {"result": True, "items": []})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert attempts == 2

    def test_authentication_errors_not_retried(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return _make_response(401, {"result": False})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        with pytest.raises(AuthenticationError):
            client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert attempts == 1

    def test_404_not_retried(self) -> None:
        attempts = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return _make_response(404, {"result": False})

        client = RaindropClient("token", transport=httpx.MockTransport(handler))
        with pytest.raises(RaindropAPIError):
            client.get_bookmarks(collection_id=1, page=0)
        client.close()
        assert attempts == 1
