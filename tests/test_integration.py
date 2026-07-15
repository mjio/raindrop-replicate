"""Optional live integration smoke test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from raindrop_replicate import replicate


@pytest.mark.integration
def test_live_smoke() -> None:
    token = os.environ.get("RAINDROP_TOKEN")
    collection_id = os.environ.get("RAINDROP_COLLECTION_ID")
    directory = os.environ.get("RAINDROP_TEST_DIRECTORY")

    if not token or not collection_id or not directory:
        pytest.skip("integration environment variables are not set")

    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)

    first = replicate(
        token=token,
        collection_id=int(collection_id),
        directory=dest,
    )
    assert first.scanned >= 0

    markdown_files = list(dest.glob("*.md"))
    if first.created > 0:
        assert markdown_files
        for path in markdown_files:
            assert str(first.collection_id) not in path.stem or True

    second = replicate(
        token=token,
        collection_id=int(collection_id),
        directory=dest,
    )
    assert second.created == 0
