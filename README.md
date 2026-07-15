# raindrop-replicate

A Python library for **idempotent, one-way, append-only replication** of Raindrop.io bookmarks into local Markdown files.

Specify a Raindrop.io collection and a target directory. Each time you run it, it adds Markdown files for bookmarks that have not yet been replicated. For example, use it to copy bookmarks to an Obsidian vault. This converts saved links into notes in a local database that can be searched, linked, and annotated.

**What it is not:** synchronization, backup, or bidirectional transfer. It does not mirror the state of Raindrop.io or refresh files when the title, tags, or URL of a bookmark change in Raindrop.io. Once a bookmark has been replicated, subsequent runs will skip it, even if you edit or delete the local file. However, missing files can be repaired during the next run. See below for more.

## Usage

```python
from datetime import UTC, datetime
from pathlib import Path
import os

from raindrop_replicate import replicate

result = replicate(
    token=os.environ["RAINDROP_TOKEN"],
    collection_id=123456789,
    directory=Path("./bookmarks"),
    until=datetime(2026, 7, 15, 16, 0, tzinfo=UTC),
)

print(result.created)
```

- Repeated calls are idempotent, already-replicated bookmarks are skipped.
- Markdown filenames are based on sanitized bookmark titles.
- Filename collisions use numeric suffixes (`Title (2).md`).
- Missing local files can be repaired on the next invocation.
- Replication state is stored in `.raindrop-replicate.json` inside the directory.

### Access token and collection ID

1. Open [Raindrop.io → Settings → Integrations](https://app.raindrop.io/settings/integrations) and create a new app.
2. Create a token for the app and use the token as `RAINDROP_TOKEN` when calling the Raindrop.io API.
3. To find your collection ID, open the collection in the Raindrop.io app and copy the number from the URL. For example, in `https://app.raindrop.io/my/123456789`, the collection ID is `123456789`.

## Development

```bash
uv sync
uv run python -m pytest
uv run ruff check .
uv run ty check .
```

Optional live smoke test (requires environment variables):

```bash
RAINDROP_TOKEN=... RAINDROP_COLLECTION_ID=... RAINDROP_TEST_DIRECTORY=... \
  uv run python -m pytest -m integration
```
