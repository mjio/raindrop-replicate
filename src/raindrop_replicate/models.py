"""Domain models for raindrop-replicate."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        msg = "timestamp must be timezone aware"
        raise ValueError(msg)
    return value


class Highlight(BaseModel):
    """A text highlight on a bookmark."""

    model_config = ConfigDict(frozen=True)

    id: str
    text: str
    note: str | None
    color: str | None
    created: datetime | None

    @field_validator("created")
    @classmethod
    def validate_created(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_aware(value)


class Bookmark(BaseModel):
    """A Raindrop bookmark."""

    model_config = ConfigDict(frozen=True)

    id: int
    collection_id: int
    title: str
    link: str
    excerpt: str
    note: str
    tags: tuple[str, ...]
    created: datetime
    last_update: datetime
    type: str
    important: bool
    highlights: tuple[Highlight, ...]

    @field_validator("created", "last_update")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)


class LedgerEntry(BaseModel):
    """A single ledger entry tracking a replicated bookmark."""

    model_config = ConfigDict(frozen=True)

    collection_id: int
    path: str
    created_at: datetime
    replicated_at: datetime

    @field_validator("created_at", "replicated_at")
    @classmethod
    def validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)


class ReplicationResult(BaseModel):
    """Result of a replicate() invocation."""

    model_config = ConfigDict(frozen=True)

    collection_id: int
    cutoff: datetime
    scanned: int
    created: int
    skipped: int
    repaired: int
    excluded_after_cutoff: int
    files_created: tuple[Path, ...] = Field(default_factory=tuple)

    @field_validator("cutoff")
    @classmethod
    def validate_cutoff(cls, value: datetime) -> datetime:
        return _require_aware(value)
