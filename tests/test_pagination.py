"""Tests for bookmark pagination behavior."""

from __future__ import annotations

import httpx

from raindrop_replicate.client import RaindropClient


def _bookmark_payload(bookmark_id: int, created: str) -> dict[str, object]:
    return {
        "_id": bookmark_id,
        "collection": {"$id": 1},
        "title": f"Bookmark {bookmark_id}",
        "link": f"https://example.com/{bookmark_id}",
        "created": created,
    }


def test_pagination_stops_on_empty_page() -> None:
    page_requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        page_requests.append(page)
        if page == "0":
            payload = {
                "result": True,
                "items": [_bookmark_payload(1, "2026-07-15T10:00:00Z")],
            }
        else:
            payload = {"result": True, "items": []}
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    client = RaindropClient("token", transport=httpx.MockTransport(handler))
    page0 = client.get_bookmarks(collection_id=1, page=0)
    page1 = client.get_bookmarks(collection_id=1, page=1)
    client.close()

    assert len(page0) == 1
    assert page1 == []
    assert page_requests == ["0", "1"]
