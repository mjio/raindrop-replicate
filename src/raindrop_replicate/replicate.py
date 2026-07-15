"""Replication orchestration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from os import PathLike
from pathlib import Path

from . import client as raindrop_client
from .exceptions import StorageConsistencyError
from .filenames import allocate_filename
from .ledger import Ledger
from .models import Bookmark, LedgerEntry, ReplicationResult
from .storage import (
    occupied_paths,
    recover_ledger,
    verify_ledger_files,
    write_bookmark_file,
)

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def normalize_cutoff(until: datetime | None) -> datetime:
    """Normalize the cutoff timestamp to UTC."""
    if until is None:
        return datetime.now(UTC)
    if until.tzinfo is None or until.tzinfo.utcoffset(until) is None:
        msg = "until must be timezone aware"
        raise ValueError(msg)
    return until.astimezone(UTC)


def replicate(
    *,
    token: str,
    collection_id: int,
    directory: str | PathLike[str],
    until: datetime | None = None,
    include_nested: bool = False,
) -> ReplicationResult:
    """Replicate bookmarks from a Raindrop collection into a local directory."""
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)

    cutoff = normalize_cutoff(until)

    ledger = Ledger.load(dest)
    ledger = recover_ledger(dest, ledger)
    verify_ledger_files(dest, ledger)

    scanned = 0
    created = 0
    skipped = 0
    repaired = 0
    excluded_after_cutoff = 0
    files_created: list[Path] = []

    with raindrop_client.RaindropClient(token) as api_client:
        page = 0
        while True:
            bookmarks = api_client.get_bookmarks(
                collection_id=collection_id,
                page=page,
                per_page=50,
                sort="created",
                nested=include_nested,
            )
            if not bookmarks:
                break

            reached_cutoff = False
            for bookmark in bookmarks:
                scanned += 1
                if bookmark.created > cutoff:
                    excluded_after_cutoff += 1
                    reached_cutoff = True
                    break

                action, path = _replicate_bookmark(
                    bookmark=bookmark,
                    directory=dest,
                    ledger=ledger,
                )
                if action == "created":
                    created += 1
                    files_created.append(path)
                elif action == "skipped":
                    skipped += 1
                elif action == "repaired":
                    repaired += 1
                    files_created.append(path)

            if reached_cutoff:
                break
            page += 1

    return ReplicationResult(
        collection_id=collection_id,
        cutoff=cutoff,
        scanned=scanned,
        created=created,
        skipped=skipped,
        repaired=repaired,
        excluded_after_cutoff=excluded_after_cutoff,
        files_created=tuple(files_created),
    )


def _replicate_bookmark(
    *,
    bookmark: Bookmark,
    directory: Path,
    ledger: Ledger,
) -> tuple[str, Path]:
    existing = ledger.get(bookmark.id)
    if existing is not None:
        file_path = directory / existing.path
        if file_path.exists():
            return "skipped", file_path

        occupant_id = _occupant_bookmark_id(file_path, directory)
        if occupant_id is not None and occupant_id != bookmark.id:
            msg = (
                f"cannot repair bookmark {bookmark.id}: "
                f"{existing.path!r} is occupied by bookmark {occupant_id}"
            )
            raise StorageConsistencyError(msg)

        path = write_bookmark_file(directory, existing.path, bookmark)
        ledger.save(directory)
        return "repaired", path

    path_name = allocate_filename(
        bookmark.title,
        directory,
        occupied_paths(directory, ledger),
    )
    path = write_bookmark_file(directory, path_name, bookmark)
    ledger.add(
        bookmark.id,
        LedgerEntry(
            collection_id=bookmark.collection_id,
            path=path_name,
            created_at=bookmark.created,
            replicated_at=datetime.now(UTC),
        ),
    )
    ledger.save(directory)
    return "created", path


def _occupant_bookmark_id(file_path: Path, directory: Path) -> int | None:
    if not file_path.exists():
        return None
    from .storage import read_raindrop_id

    return read_raindrop_id(file_path)
