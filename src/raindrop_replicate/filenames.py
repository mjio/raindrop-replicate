from __future__ import annotations

import re
import unicodedata
from pathlib import Path

WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

FORBIDDEN_CHARS_RE = re.compile(r'[/\\:*?"<>|]')
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"\s+")


def sanitize_title(title: str) -> str:
    """Sanitize a bookmark title for use as a Markdown filename stem."""
    normalized = unicodedata.normalize("NFC", title).strip()
    normalized = CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = FORBIDDEN_CHARS_RE.sub(" ", normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized).strip(" .")
    if not normalized:
        normalized = "Untitled"
    if normalized.upper() in WINDOWS_RESERVED:
        normalized = f"_{normalized}"
    if len(normalized) > 180:
        normalized = normalized[:180].rstrip(" .")
        if not normalized:
            normalized = "Untitled"
    return normalized


def filename_for_title(title: str, suffix: int = 1) -> str:
    """Build a filename for a sanitized title and numeric suffix."""
    stem = sanitize_title(title)
    if suffix <= 1:
        return f"{stem}.md"
    return f"{stem} ({suffix}).md"


def allocate_filename(
    title: str,
    directory: Path,
    occupied_paths: set[str],
) -> str:
    """Allocate a unique Markdown filename for a bookmark title."""
    stem = sanitize_title(title)
    for occupied in occupied_paths:
        occupied_stem = Path(occupied).stem
        if occupied_stem.casefold() == stem.casefold():
            stem = occupied_stem
            break

    occupied_lower = {path.casefold() for path in occupied_paths}
    suffix = 1
    while True:
        candidate = filename_for_title(stem, suffix)
        candidate_path = directory / candidate
        if candidate.casefold() in occupied_lower:
            suffix += 1
            continue
        if candidate_path.exists():
            suffix += 1
            continue
        return candidate
