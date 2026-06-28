# Orchestration (Dagster)

Dagster ties the whole pipeline together as a lineage-connected asset graph:

```
raw.gh_events (dlt, hourly-partitioned)
        │
        ▼
stg_events / quarantine_events  →  int_repo_daily_activity  →  dim_*, fact_events, agg_daily_repo_momentum
                                   (dbt models; tests surface as Dagster asset checks)
```

- **`raw_gh_events`** — one GH Archive hour per partition, loaded via the dlt
  pipeline. Idempotent (merge on `event_id`).
- **`pulsedb_dbt_assets`** — the Silver/Gold dbt models + tests, run as
  `dbt build`. Elementary models are excluded from the graph to keep it focused.
- **Run metadata** — every materialization appends to `meta.pipeline_runs`
  (rows, duration, status); the dashboard's pipeline-health page reads it.
- **Failure alerting** — `github_issue_on_failure` opens a GitHub issue on any
  run failure. Inert (logs only) until `GITHUB_TOKEN` + `GITHUB_REPOSITORY` are set.

## Run the UI

```bash
export DAGSTER_HOME="$(cygpath -m "$(pwd)/.dagster_home")"   # Git Bash on Windows
uv run dagster dev -m orchestration.definitions
# open http://localhost:3000
```

> The dbt manifest must exist first: `cd transform && uv run dbt parse --profiles-dir .`

## Materialize / backfill from the CLI

```bash
# one hour
uv run dagster asset materialize --select "raw/gh_events" \
  --partition "2024-01-15-15:00" -m orchestration.definitions

# rebuild Silver/Gold
uv run dagster job execute -j dbt_transform_job -m orchestration.definitions

# backfill a range of hours (UI: Overview → Backfills, or CLI):
uv run dagster job backfill -j bronze_ingest_job \
  --from "2024-01-15-00:00" --to "2024-01-15-23:00" -m orchestration.definitions
```

## Schedules

| Schedule | Cron | What |
|---|---|---|
| `bronze_ingest_job` | hourly | ingest the latest GH Archive hour |
| `dbt_transform_job` | `7 1 * * *` | rebuild Silver/Gold (incremental) + tests daily |
