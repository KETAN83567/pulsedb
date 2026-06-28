"""Persistent run-metadata logging to `meta.pipeline_runs` in DuckDB.

Every asset materialization appends a row here: what ran, for which partition,
how long it took, how many rows, and success/failure. The dashboard's
pipeline-health page reads this table.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import duckdb

from .project import DB_PATH

_DDL = """
create schema if not exists meta;
create table if not exists meta.pipeline_runs (
    run_id varchar,
    asset varchar,
    partition varchar,
    status varchar,
    rows bigint,
    duration_s double,
    error varchar,
    recorded_at timestamptz
);
"""


def record_run(
    *,
    run_id: str,
    asset: str,
    partition: str | None,
    status: str,
    rows: int | None,
    duration_s: float,
    error: str | None = None,
) -> None:
    """Append one run-metadata row. Best-effort: retries briefly if the DuckDB
    file is momentarily locked by another writer, then gives up without raising
    (metadata logging must never fail the actual pipeline)."""
    row = (
        run_id,
        asset,
        partition,
        status,
        rows,
        duration_s,
        (error or "")[:2000] or None,
        datetime.now(timezone.utc),
    )
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            con = duckdb.connect(str(DB_PATH))
            try:
                con.execute(_DDL)
                con.execute(
                    "insert into meta.pipeline_runs values (?, ?, ?, ?, ?, ?, ?, ?)",
                    row,
                )
            finally:
                con.close()
            return
        except duckdb.IOException as exc:  # file locked by another connection
            last_err = exc
            time.sleep(0.5 * (attempt + 1))
    print(f"[metadata] WARN: could not record run after retries: {last_err}")
