"""Tests for Markdown rendering."""

from __future__ import annotations

from datetime import UTC, datetime

from raindrop_replicate.markdown import render_markdown
from raindrop_replicate.models import Bookmark, Highlight


def test_normal_article(sample_bookmark: Bookmark) -> None:
    content = render_markdown(sample_bookmark)
    assert content.startswith("---\n")
    assert "raindrop_id: 123456789" in content
    assert 'title: "Understanding Agent Loops"' in content
    assert 'url: "https://example.com/article"' in content
    assert 'created: "2026-07-15T12:30:00Z"' in content
    assert 'tags: ["agents", "python"]' in content
    assert "# Understanding Agent Loops" in content
    assert "## Note" in content
    assert "## Highlights" in content
    assert "> First highlighted passage." in content


def test_empty_note() -> None:
    bookmark = Bookmark(
        id=1,
        collection_id=2,
        title="Title",
        link="https://example.com",
        excerpt="Excerpt",
        note="",
        tags=(),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(),
    )
    content = render_markdown(bookmark)
    assert "## Note" not in content


def test_empty_highlights() -> None:
    bookmark = Bookmark(
        id=1,
        collection_id=2,
        title="Title",
        link="https://example.com",
        excerpt="",
        note="",
        tags=(),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(),
    )
    content = render_markdown(bookmark)
    assert "## Highlights" not in content


def test_quotes_and_newlines_in_metadata() -> None:
    bookmark = Bookmark(
        id=1,
        collection_id=2,
        title='Say "hello"\nworld',
        link='https://example.com?q="1"',
        excerpt="",
        note="",
        tags=('tag with "quotes"',),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(),
    )
    content = render_markdown(bookmark)
    assert 'title: "Say \\"hello\\"\\nworld"' in content
    assert 'url: "https://example.com?q=\\"1\\""' in content


def test_unicode_titles_and_tags() -> None:
    bookmark = Bookmark(
        id=1,
        collection_id=2,
        title="日本語タイトル",
        link="https://example.com",
        excerpt="",
        note="",
        tags=("タグ",),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(),
    )
    content = render_markdown(bookmark)
    assert "# 日本語タイトル" in content
    assert "tags:" in content
    assert "\\u30bf\\u30b0" in content


def test_multiple_highlights() -> None:
    bookmark = Bookmark(
        id=1,
        collection_id=2,
        title="Title",
        link="https://example.com",
        excerpt="",
        note="",
        tags=(),
        created=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        last_update=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        type="article",
        important=False,
        highlights=(
            Highlight(id="1", text="One", note=None, color=None, created=None),
            Highlight(id="2", text="Two", note="note", color=None, created=None),
        ),
    )
    content = render_markdown(bookmark)
    assert "> One" in content
    assert "> Two" in content
    assert "note" in content


def test_final_newline(sample_bookmark: Bookmark) -> None:
    content = render_markdown(sample_bookmark)
    assert content.endswith("\n")
    assert not content.endswith("\n\n")
