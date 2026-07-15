from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from .exceptions import AuthenticationError, RaindropAPIError, RaindropResponseError
from .models import Bookmark, Highlight

logger: logging.Logger = logging.getLogger(name=__name__)

BASE_URL: str = "https://api.raindrop.io"
MAX_RETRIES: int = 3

DEFAULT_TIMEOUT: httpx.Timeout = httpx.Timeout(
    connect=10.0,
    read=30.0,
    write=30.0,
    pool=10.0,
)


def parse_timestamp(value: object, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp from the Raindrop.io API."""
    if not isinstance(value, str):
        msg = f"{field_name} must be a string timestamp"
        raise RaindropResponseError(msg)
    try:
        normalized: str = value.replace("Z", "+00:00")
        parsed: datetime = datetime.fromisoformat(normalized)
    except ValueError as exc:
        msg = f"invalid timestamp for {field_name}: {value!r}"
        raise RaindropResponseError(msg) from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        msg = f"{field_name} must be timezone aware"
        raise RaindropResponseError(msg)
    return parsed.astimezone(tz=UTC)


def parse_highlight(data: dict[str, Any]) -> Highlight:
    """Parse a highlight object from the API."""
    highlight_id = data.get("_id")
    text = data.get("text")
    if not isinstance(highlight_id, str):
        msg = "highlight is missing _id"
        raise RaindropResponseError(msg)
    if not isinstance(text, str):
        msg = "highlight is missing text"
        raise RaindropResponseError(msg)

    note = data.get("note")
    color = data.get("color")
    created_raw = data.get("created")
    created = (
        parse_timestamp(created_raw, "highlight.created")
        if created_raw is not None
        else None
    )

    return Highlight(
        id=highlight_id,
        text=text,
        note=note if isinstance(note, str) else None,
        color=color if isinstance(color, str) else None,
        created=created,
    )


def parse_bookmark(data: dict[str, Any]) -> Bookmark:
    """Parse a bookmark object from the API using documented fields only."""
    bookmark_id = data.get("_id")
    if not isinstance(bookmark_id, int):
        msg = "bookmark is missing _id"
        raise RaindropResponseError(msg)

    collection = data.get("collection")
    if not isinstance(collection, dict):
        msg = "bookmark is missing collection"
        raise RaindropResponseError(msg)
    collection_id = collection.get("$id")
    if not isinstance(collection_id, int):
        msg = "bookmark is missing collection.$id"
        raise RaindropResponseError(msg)

    link = data.get("link")
    if not isinstance(link, str):
        msg = "bookmark is missing link"
        raise RaindropResponseError(msg)

    title = data.get("title")
    if not isinstance(title, str):
        msg = "bookmark is missing title"
        raise RaindropResponseError(msg)

    if "created" not in data:
        msg = "bookmark is missing created"
        raise RaindropResponseError(msg)
    created = parse_timestamp(data["created"], "created")

    last_update_raw = data.get("lastUpdate")
    last_update = (
        parse_timestamp(last_update_raw, "lastUpdate")
        if last_update_raw is not None
        else created
    )

    excerpt = data.get("excerpt")
    note = data.get("note")
    tags_raw = data.get("tags")
    bookmark_type = data.get("type")
    important = data.get("important")
    highlights_raw = data.get("highlights")

    tags: tuple[str, ...] = ()
    if isinstance(tags_raw, list):
        tags = tuple(tag for tag in tags_raw if isinstance(tag, str))

    highlights: tuple[Highlight, ...] = ()
    if isinstance(highlights_raw, list):
        highlights = tuple(
            parse_highlight(item) for item in highlights_raw if isinstance(item, dict)
        )

    return Bookmark(
        id=bookmark_id,
        collection_id=collection_id,
        title=title,
        link=link,
        excerpt=excerpt if isinstance(excerpt, str) else "",
        note=note if isinstance(note, str) else "",
        tags=tags,
        created=created,
        last_update=last_update,
        type=bookmark_type if isinstance(bookmark_type, str) else "",
        important=important if isinstance(important, bool) else False,
        highlights=highlights,
    )


def parse_bookmarks_response(payload: object) -> list[Bookmark]:
    """Parse a paginated raindrops API response."""
    if not isinstance(payload, dict):
        msg = "response must be a JSON object"
        raise RaindropResponseError(msg)

    result = payload.get("result")
    if result is not True:
        msg = "response result is not true"
        raise RaindropResponseError(msg)

    items = payload.get("items")
    if not isinstance(items, list):
        msg = "response items must be a list"
        raise RaindropResponseError(msg)

    bookmarks: list[Bookmark] = []
    for item in items:
        if isinstance(item, dict):
            bookmarks.append(parse_bookmark(cast(dict[str, Any], item)))
    return bookmarks


class RaindropClient:
    """HTTP client for the Raindrop.io API."""

    def __init__(
        self,
        token: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = token
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            transport=transport,
            headers={"Authorization": f"Bearer {token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RaindropClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_bookmarks(
        self,
        *,
        collection_id: int,
        page: int,
        per_page: int = 50,
        sort: str = "created",
        nested: bool = False,
    ) -> list[Bookmark]:
        """Fetch one page of bookmarks from a collection."""
        params: dict[str, str | int] = {
            "sort": sort,
            "page": page,
            "perpage": per_page,
            "nested": str(nested).lower(),
        }
        response = self._request_with_retries(
            "GET",
            f"/rest/v1/raindrops/{collection_id}",
            params=params,
        )
        return parse_bookmarks_response(response.json())

    def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self._client.request(method, url, params=params)
            except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                last_error = exc
                if attempt >= MAX_RETRIES:
                    raise RaindropAPIError("request timed out") from exc
                self._backoff(attempt)
                continue

            if response.status_code in {401, 403}:
                raise AuthenticationError(
                    f"authentication failed with status {response.status_code}"
                )
            if response.status_code == 429:
                if attempt >= MAX_RETRIES:
                    raise RaindropAPIError("rate limit exceeded") from None
                self._wait_for_rate_limit(response, attempt)
                continue
            if response.status_code in {500, 502, 503, 504}:
                if attempt >= MAX_RETRIES:
                    raise RaindropAPIError(
                        f"server error with status {response.status_code}"
                    ) from None
                self._backoff(attempt)
                continue
            if response.status_code >= 400:
                raise RaindropAPIError(
                    f"request failed with status {response.status_code}"
                )

            return response

        raise RaindropAPIError("request failed after retries") from last_error

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(2**attempt)

    @staticmethod
    def _wait_for_rate_limit(response: httpx.Response, attempt: int) -> None:
        reset_header = response.headers.get("X-RateLimit-Reset")
        if reset_header is not None:
            try:
                reset_at = float(reset_header)
                delay = max(reset_at - time.time(), 0.0)
                if delay > 0:
                    time.sleep(delay)
                    return
            except ValueError:
                pass
        time.sleep(2**attempt)
