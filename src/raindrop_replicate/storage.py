"""Atomic file storage and crash recovery."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from .exceptions import StorageConsistencyError
from .ledger import Ledger
from .markdown import render_markdown
from .models import Bookmark, LedgerEntry

RAINDROP_ID_RE = re.compile(r"^raindrop_id:\s*(\d+)\s*$", re.MULTILINE)
COLLECTION_ID_RE = re.compile(r"^collection_id:\s*(\d+)\s*$", re.MULTILINE)
CREATED_RE = re.compile(r'^created:\s*"([^"]+)"\s*$', re.MULTILINE)


def atomic_write_text(path: Path, content: str) -> None:
    """Write text to a path atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def read_raindrop_id(path: Path) -> int | None:
    """Read raindrop_id from a Markdown file's front matter."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    front_matter = text[3:end]
    match = RAINDROP_ID_RE.search(front_matter)
    if match is None:
        return None
    return int(match.group(1))


def scan_front_matter(directory: Path) -> dict[int, Path]:
    """Scan top-level Markdown files and map bookmark IDs to paths."""
    mapping: dict[int, Path] = {}
    for path in sorted(directory.glob("*.md")):
        bookmark_id = read_raindrop_id(path)
        if bookmark_id is None:
            continue
        if bookmark_id in mapping:
            other = mapping[bookmark_id].name
            msg = f"duplicate raindrop_id {bookmark_id} in {path.name} and {other}"
            raise StorageConsistencyError(msg)
        mapping[bookmark_id] = path
    return mapping


def _parse_front_matter_field(text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(text)
    if match is None:
        return None
    return match.group(1)


def recover_ledger(directory: Path, ledger: Ledger) -> Ledger:
    """Recover missing ledger entries from Markdown front matter."""
    front_matter_map = scan_front_matter(directory)
    recovered = dict(ledger.entries)

    for bookmark_id, path in front_matter_map.items():
        key = str(bookmark_id)
        if key in recovered:
            if recovered[key].path != path.name:
                msg = (
                    f"ledger path {recovered[key].path!r} does not match "
                    f"front matter in {path.name!r} for raindrop_id {bookmark_id}"
                )
                raise StorageConsistencyError(msg)
            file_id = read_raindrop_id(path)
            if file_id is not None and file_id != bookmark_id:
                msg = (
                    f"ledger entry for {bookmark_id} points to {path.name!r} "
                    f"with raindrop_id {file_id}"
                )
                raise StorageConsistencyError(msg)
            continue

        text = path.read_text(encoding="utf-8")
        end = text.find("\n---", 3)
        front_matter = text[3:end] if text.startswith("---") and end != -1 else ""

        collection_raw = _parse_front_matter_field(front_matter, COLLECTION_ID_RE)
        collection_id = int(collection_raw) if collection_raw is not None else 0

        created_raw = _parse_front_matter_field(front_matter, CREATED_RE)
        if created_raw is not None:
            created_at = datetime.fromisoformat(
                created_raw.replace("Z", "+00:00")
            ).astimezone(UTC)
        else:
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)

        stat = path.stat()
        replicated_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        recovered[key] = LedgerEntry(
            collection_id=collection_id,
            path=path.name,
            created_at=created_at,
            replicated_at=replicated_at,
        )

    return Ledger(recovered)


def verify_ledger_files(directory: Path, ledger: Ledger) -> None:
    """Verify ledger entries match on-disk front matter."""
    front_matter_map = scan_front_matter(directory)
    for bookmark_id, entry in ledger.entries.items():
        numeric_id = int(bookmark_id)
        path = front_matter_map.get(numeric_id)
        if path is None:
            continue
        if path.name != entry.path:
            msg = (
                f"ledger path {entry.path!r} does not match "
                f"front matter in {path.name!r} for raindrop_id {numeric_id}"
            )
            raise StorageConsistencyError(msg)


def write_bookmark_file(directory: Path, path_name: str, bookmark: Bookmark) -> Path:
    """Write a bookmark Markdown file atomically."""
    final_path = directory / path_name
    atomic_write_text(final_path, render_markdown(bookmark))
    return final_path


def occupied_paths(directory: Path, ledger: Ledger) -> set[str]:
    """Return occupied filenames from the ledger and existing files."""
    occupied = set(ledger.paths())
    for path in directory.glob("*.md"):
        occupied.add(path.name)
    return occupied
