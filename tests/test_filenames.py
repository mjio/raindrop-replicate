"""Tests for filename sanitization and collision handling."""

from __future__ import annotations

from pathlib import Path

from raindrop_replicate.filenames import (
    allocate_filename,
    filename_for_title,
    sanitize_title,
)


def test_slashes_and_forbidden_characters() -> None:
    assert sanitize_title("foo/bar:baz") == "foo bar baz"
    assert sanitize_title('a*b?c"d<e>f|g\\h') == "a b c d e f g h"


def test_unicode_titles() -> None:
    assert sanitize_title("Café résumé") == "Café résumé"
    assert "/" not in sanitize_title("日本語/タイトル")


def test_empty_title() -> None:
    assert sanitize_title("") == "Untitled"
    assert sanitize_title("   ") == "Untitled"


def test_control_characters() -> None:
    assert sanitize_title("hello\x00world") == "hello world"


def test_excessively_long_title() -> None:
    long_title = "a" * 200
    sanitized = sanitize_title(long_title)
    assert len(sanitized) <= 180


def test_reserved_windows_names() -> None:
    assert sanitize_title("CON") == "_CON"
    assert sanitize_title("com1") == "_com1"
    assert sanitize_title("LPT9") == "_LPT9"


def test_duplicate_titles(tmp_path: Path) -> None:
    first = allocate_filename("Article About Agents", tmp_path, set())
    second = allocate_filename("Article About Agents", tmp_path, {first})
    assert first == "Article About Agents.md"
    assert second == "Article About Agents (2).md"


def test_case_insensitive_collisions(tmp_path: Path) -> None:
    occupied = {"Article About Agents.md"}
    candidate = allocate_filename("article about agents", tmp_path, occupied)
    assert candidate == "Article About Agents (2).md"


def test_three_or_more_identical_titles(tmp_path: Path) -> None:
    occupied = {"Article About Agents.md", "Article About Agents (2).md"}
    candidate = allocate_filename("Article About Agents", tmp_path, occupied)
    assert candidate == "Article About Agents (3).md"


def test_existing_unrelated_files(tmp_path: Path) -> None:
    existing = tmp_path / "Article About Agents.md"
    existing.write_text("untracked", encoding="utf-8")
    candidate = allocate_filename("Article About Agents", tmp_path, set())
    assert candidate == "Article About Agents (2).md"


def test_filename_does_not_contain_raindrop_id() -> None:
    title = "Understanding Agent Loops"
    bookmark_id = 123456789
    assert str(bookmark_id) not in filename_for_title(title)
    assert str(bookmark_id) not in filename_for_title(title, suffix=2)
