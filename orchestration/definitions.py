"""Dagster Definitions: assets, jobs, schedules, the failure sensor, resources.

Load with:  uv run dagster dev -m orchestration.definitions
"""

from dagster import (
    AssetSelection,
    Definitions,
    ScheduleDefinition,
    build_schedule_from_partitioned_job,
    define_asset_job,
)
from dagster_dbt import DbtCliResource

from .alerts import github_issue_on_failure
from .assets import hourly_partitions, pulsedb_dbt_assets, raw_gh_events
from .project import dbt_project

# Ingest one GH Archive hour per partition; schedule fires hourly and backfills.
bronze_ingest_job = define_asset_job(
    "bronze_ingest_job",
    selection=AssetSelection.assets(raw_gh_events),
    partitions_def=hourly_partitions,
)
bronze_ingest_schedule = build_schedule_from_partitioned_job(bronze_ingest_job)

# Rebuild Silver/Gold (incremental) + run tests. Daily at 01:07 (off the hour).
dbt_transform_job = define_asset_job(
    "dbt_transform_job",
    selection=AssetSelection.assets(pulsedb_dbt_assets),
)
dbt_transform_schedule = ScheduleDefinition(
    job=dbt_transform_job,
    cron_schedule="7 1 * * *",
)

defs = Definitions(
    assets=[raw_gh_events, pulsedb_dbt_assets],
    jobs=[bronze_ingest_job, dbt_transform_job],
    schedules=[bronze_ingest_schedule, dbt_transform_schedule],
    sensors=[github_issue_on_failure],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
