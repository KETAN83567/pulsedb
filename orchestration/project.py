"""Shared paths + the dagster-dbt project handle.

The dbt manifest powers per-model lineage in the Dagster asset graph. In dev
(`dagster dev`) it is regenerated automatically; for CLI/CI runs build it once
with `cd transform && uv run dbt parse --profiles-dir .`.
"""

from __future__ import annotations

from pathlib import Path

from dagster_dbt import DbtProject

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRANSFORM_DIR = PROJECT_ROOT / "transform"
DB_PATH = PROJECT_ROOT / "pulsedb.duckdb"

# First GH Archive hour we treat as the start of the partition space.
PARTITION_START = "2024-01-15-00:00"

dbt_project = DbtProject(
    project_dir=TRANSFORM_DIR,
    profiles_dir=TRANSFORM_DIR,
    target="dev",
)
dbt_project.prepare_if_dev()
