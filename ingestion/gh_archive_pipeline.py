"""Ingest one hour of GH Archive events into DuckDB as `raw.gh_events` (bronze layer).

GH Archive publishes one gzip-compressed JSON-lines file per hour at
`https://data.gharchive.org/<YYYY-MM-DD-H>.json.gz` (hour is NOT zero-padded).
Each line is a single public GitHub event.

Design (see project notes Part B §5, §7):
- Bronze keeps ALL events but only the lightweight columns we need for momentum metrics,
  plus the one nested field that matters (`payload.action`, e.g. PR opened/closed). We do
  NOT store the full multi-KB event payloads (commit/PR/issue bodies) -- doing so ballooned
  DuckDB to ~2.2 GB per hour. Schematizing at ingest is the right tradeoff for a local project.
- Idempotent: dlt `merge` on `event_id` means re-running the same hour adds no duplicates.
- Streaming decompress (line-by-line) keeps memory flat regardless of file size.

Usage:  uv run python ingestion/gh_archive_pipeline.py [YYYY-MM-DD-H]
Set GH_MAX_EVENTS=N to cap rows for fast dev/CI runs (default: unlimited = full hour).
"""

from __future__ import annotations

import gzip
import json
import os
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import dlt
import requests

# DuckDB warehouse file at the project root, regardless of the caller's cwd.
DB_PATH = str(Path(__file__).resolve().parents[1] / "pulsedb.duckdb")
DEFAULT_DATE_HOUR = "2024-01-15-15"
GHARCHIVE_URL = "https://data.gharchive.org/{date_hour}.json.gz"


def _to_row(event: dict, source_file: str, loaded_at: str) -> dict:
    """Project a raw GH event into a lightweight bronze row (no heavy payload bodies)."""
    actor = event.get("actor") or {}
    repo = event.get("repo") or {}
    payload = event.get("payload") or {}
    return {
        "event_id": event.get("id"),
        "event_type": event.get("type"),
        "actor_id": actor.get("id"),
        "actor_login": actor.get("login"),
        "repo_id": repo.get("id"),
        "repo_name": repo.get("name"),
        "created_at": event.get("created_at"),
        "payload_action": payload.get("action"),  # e.g. opened/closed/started; null for many types
        "_source_file": source_file,
        "_loaded_at": loaded_at,
    }


@dlt.resource(name="gh_events", write_disposition="merge", primary_key="event_id")
def gh_events(date_hour: str) -> Iterator[dict]:
    """Stream and yield one hour of GH Archive events as bronze rows."""
    url = GHARCHIVE_URL.format(date_hour=date_hour)
    source_file = f"{date_hour}.json.gz"
    loaded_at = datetime.now(timezone.utc).isoformat()

    max_events = int(os.environ.get("GH_MAX_EVENTS", "0"))  # 0 = unlimited

    with requests.get(url, stream=True, timeout=180) as resp:
        resp.raise_for_status()
        # GH Archive files are gzip *content* (not HTTP transfer-encoding), so decompress ourselves.
        resp.raw.decode_content = False
        with gzip.GzipFile(fileobj=resp.raw) as gz:
            for i, line in enumerate(gz):
                if max_events and i >= max_events:
                    break
                event = json.loads(line)
                yield _to_row(event, source_file, loaded_at)


def run(date_hour: str) -> None:
    pipeline = dlt.pipeline(
        pipeline_name="gh_archive",
        destination=dlt.destinations.duckdb(DB_PATH),
        dataset_name="raw",
    )
    info = pipeline.run(gh_events(date_hour))
    print(info)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DATE_HOUR)
