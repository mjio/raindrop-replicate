"""JSON ledger for tracking replicated bookmarks."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .exceptions import LedgerFormatError
from .models import LedgerEntry

LEDGER_FILENAME = ".raindrop-replicate.json"
LEDGER_TMP_SUFFIX = ".tmp"
SUPPORTED_VERSION = 1


class Ledger:
    """In-memory ledger backed by a JSON file."""

    def __init__(self, entries: dict[str, LedgerEntry]) -> None:
        self._entries = entries

    @property
    def entries(self) -> dict[str, LedgerEntry]:
        return self._entries

    def contains(self, bookmark_id: int) -> bool:
        return str(bookmark_id) in self._entries

    def get(self, bookmark_id: int) -> LedgerEntry | None:
        return self._entries.get(str(bookmark_id))

    def add(self, bookmark_id: int, entry: LedgerEntry) -> None:
        self._entries[str(bookmark_id)] = entry

    def paths(self) -> set[str]:
        return {entry.path for entry in self._entries.values()}

    @classmethod
    def load(cls, directory: Path) -> Ledger:
        path = directory / LEDGER_FILENAME
        if not path.exists():
            return cls({})
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LedgerFormatError("ledger contains invalid JSON") from exc
        return cls(_parse_ledger(raw))

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SUPPORTED_VERSION,
            "entries": {
                bookmark_id: _entry_to_dict(entry)
                for bookmark_id, entry in sorted(
                    self._entries.items(), key=lambda item: item[0]
                )
            },
        }
        tmp_path = directory / f"{LEDGER_FILENAME}{LEDGER_TMP_SUFFIX}"
        final_path = directory / LEDGER_FILENAME
        serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, final_path)


def _parse_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        msg = f"{field_name} must be a string timestamp"
        raise LedgerFormatError(msg)
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        msg = f"invalid timestamp for {field_name}: {value!r}"
        raise LedgerFormatError(msg) from exc
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        msg = f"{field_name} must be timezone aware"
        raise LedgerFormatError(msg)
    return parsed.astimezone(UTC)


def _entry_to_dict(entry: LedgerEntry) -> dict[str, object]:
    return {
        "collection_id": entry.collection_id,
        "path": entry.path,
        "created_at": entry.created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "replicated_at": entry.replicated_at.astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }


def _parse_ledger(raw: object) -> dict[str, LedgerEntry]:
    if not isinstance(raw, dict):
        raise LedgerFormatError("ledger must be a JSON object")

    version = raw.get("version")
    if version != SUPPORTED_VERSION:
        raise LedgerFormatError(f"unsupported ledger version: {version!r}")

    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, dict):
        raise LedgerFormatError("ledger entries must be an object")

    entries: dict[str, LedgerEntry] = {}
    seen_paths: set[str] = set()

    for bookmark_id, entry_raw in entries_raw.items():
        if not isinstance(bookmark_id, str) or not bookmark_id.isdigit():
            raise LedgerFormatError(f"invalid bookmark id: {bookmark_id!r}")
        if not isinstance(entry_raw, dict):
            raise LedgerFormatError(f"invalid entry for bookmark {bookmark_id!r}")

        path = entry_raw.get("path")
        collection_id = entry_raw.get("collection_id")
        created_at = entry_raw.get("created_at")
        replicated_at = entry_raw.get("replicated_at")

        if not isinstance(path, str) or not path:
            raise LedgerFormatError(f"invalid path for bookmark {bookmark_id!r}")
        if not isinstance(collection_id, int):
            raise LedgerFormatError(
                f"invalid collection_id for bookmark {bookmark_id!r}"
            )

        path_key = path.casefold()
        if path_key in seen_paths:
            raise LedgerFormatError(f"duplicate ledger path: {path!r}")
        seen_paths.add(path_key)

        entries[bookmark_id] = LedgerEntry(
            collection_id=collection_id,
            path=path,
            created_at=_parse_timestamp(created_at, "created_at"),
            replicated_at=_parse_timestamp(replicated_at, "replicated_at"),
        )

    return entries
