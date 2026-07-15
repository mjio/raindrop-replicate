"""Markdown rendering for bookmarks."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from .models import Bookmark, Highlight


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _yaml_scalar(value: object) -> str:
    return json.dumps(value)


def _render_highlight(highlight: Highlight) -> str:
    lines = [f"> {highlight.text}"]
    if highlight.note:
        lines.append("")
        lines.append(highlight.note)
    return "\n".join(lines)


def render_markdown(bookmark: Bookmark) -> str:
    """Render a bookmark as Markdown with YAML front matter."""
    front_matter = [
        "---",
        f"raindrop_id: {bookmark.id}",
        f"collection_id: {bookmark.collection_id}",
        f"title: {_yaml_scalar(bookmark.title)}",
        f"url: {_yaml_scalar(bookmark.link)}",
        f"created: {_yaml_scalar(_format_timestamp(bookmark.created))}",
        f"last_update: {_yaml_scalar(_format_timestamp(bookmark.last_update))}",
        f"type: {_yaml_scalar(bookmark.type)}",
        f"important: {str(bookmark.important).lower()}",
        f"tags: {json.dumps(list(bookmark.tags))}",
        "---",
        "",
        f"# {bookmark.title}",
        "",
    ]

    if bookmark.excerpt:
        front_matter.append(bookmark.excerpt)
        front_matter.append("")

    if bookmark.note:
        front_matter.extend(["## Note", "", bookmark.note, ""])

    if bookmark.highlights:
        front_matter.extend(["## Highlights", ""])
        for index, highlight in enumerate(bookmark.highlights):
            if index > 0:
                front_matter.append("")
            front_matter.append(_render_highlight(highlight))
        front_matter.append("")

    content = "\n".join(front_matter).rstrip("\n") + "\n"
    return content
