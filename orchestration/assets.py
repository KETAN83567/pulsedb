"""Dagster assets: partitioned bronze ingestion (dlt) + the dbt model graph.

The bronze asset's key is ["raw", "gh_events"], which matches how dagster-dbt
keys the dbt `raw.gh_events` source — so the dbt models automatically depend on
it and the lineage connects end-to-end.
"""

import time
from datetime import datetime

import duckdb
from dagster import (
    AssetExecutionContext,
    AssetKey,
    HourlyPartitionsDefinition,
    MaterializeResult,
    MetadataValue,
    asset,
)
from dagster_dbt import DbtCliResource, dbt_assets

from ingestion.gh_archive_pipeline import run as run_ingestion

from .metadata import record_run
from .project import DB_PATH, PARTITION_START, dbt_project

# One partition per GH Archive hour.
hourly_partitions = HourlyPartitionsDefinition(start_date=PARTITION_START)


def _partition_to_date_hour(partition_key: str) -> str:
    """Dagster hourly key '%Y-%m-%d-%H:%M' -> GH Archive 'YYYY-MM-DD-H'
    (hour is NOT zero-padded, matching gharchive.org filenames)."""
    dt = datetime.strptime(partition_key, "%Y-%m-%d-%H:%M")
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d}-{dt.hour}"


@asset(
    key=AssetKey(["raw", "gh_events"]),
    partitions_def=hourly_partitions,
    group_name="ingestion",
    description="Bronze: one GH Archive hour loaded into raw.gh_events via dlt (idempotent merge).",
    compute_kind="dlt",
)
def raw_gh_events(context: AssetExecutionContext) -> MaterializeResult:
    date_hour = _partition_to_date_hour(context.partition_key)
    started = time.time()
    status, error, rows = "success", None, 0
    try:
        run_ingestion(date_hour)
        con = duckdb.connect(str(DB_PATH))
        try:
            rows = con.execute(
                "select count(*) from raw.gh_events where _source_file = ?",
                [f"{date_hour}.json.gz"],
            ).fetchone()[0]
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001 - record then re-raise for the sensor
        status, error = "failure", str(exc)
        raise
    finally:
        duration = time.time() - started
        record_run(
            run_id=context.run_id,
            asset="raw.gh_events",
            partition=context.partition_key,
            status=status,
            rows=rows,
            duration_s=duration,
            error=error,
        )
    return MaterializeResult(
        metadata={
            "date_hour": date_hour,
            "rows_in_partition": MetadataValue.int(rows),
            "duration_s": MetadataValue.float(round(duration, 2)),
        }
    )


@dbt_assets(
    manifest=dbt_project.manifest_path,
    exclude="package:elementary",  # keep the observability models out of the graph
)
def pulsedb_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Silver + Gold models and their tests, run as `dbt build`."""
    started = time.time()
    status, error = "success", None
    try:
        yield from dbt.cli(["build"], context=context).stream()
    except Exception as exc:  # noqa: BLE001
        status, error = "failure", str(exc)
        raise
    finally:
        record_run(
            run_id=context.run_id,
            asset="dbt_build",
            partition=None,
            status=status,
            rows=None,
            duration_s=time.time() - started,
            error=error,
        )
