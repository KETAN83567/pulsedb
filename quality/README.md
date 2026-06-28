# Data Quality & Observability

PulseDB's quality layer is **dbt-native** (Elementary), layered on top of the
dbt tests already defined alongside the models. No enterprise SaaS — everything
runs locally and in CI.

## What's enforced

| Check | Where | What it catches |
|---|---|---|
| **Schema contract** (`not_null`, `unique`, types) | `transform/models/**/_*.yml` | Bad/missing keys, dupes |
| **Row quarantine** | `stg_events` / `quarantine_events` | Contract-failing rows are routed aside, never silently dropped |
| **Reconciliation invariant** | `transform/tests/assert_bronze_reconciliation.sql` | `raw == stg + quarantine` (no data loss in Silver) |
| **Grain uniqueness** | `transform/tests/assert_momentum_grain_unique.sql` | Duplicate (repo, day) rows in the gold aggregate |
| **FK integrity** | `relationships` tests | Orphan facts with no matching dimension |
| **Source freshness** | `_staging__sources.yml` (`_loaded_at`) | Pipeline stopped loading (SLA: warn 24h / error 48h) |
| **Volume anomalies** | Elementary `volume_anomalies` on `stg_events` | Sudden drop/spike in event volume vs. learned baseline |
| **Schema drift** | Elementary `schema_changes` on `stg_events` | Columns added/removed/retyped upstream |

Elementary logs every run + test result to the `main_elementary` schema, which
powers anomaly baselines and the HTML report below.

## Run the checks

```bash
cd transform
uv run dbt build --profiles-dir .          # models + all tests (incl. Elementary)
uv run dbt source freshness --profiles-dir .
```

## Generate the observability report

The `edr` CLI renders an interactive HTML report. It runs dbt from a different
working directory, so point it at the **absolute** warehouse path:

```bash
# install once (isolated):  uv tool install 'elementary-data[duckdb]==0.25.0'
cd transform
export PULSEDB_DUCKDB="$(cygpath -m "$(cd .. && pwd)/pulsedb.duckdb")"   # Git Bash on Windows
edr report --profiles-dir . --target-path ../quality/elementary_report
# -> opens ../quality/elementary_report/elementary_report.html
```

The report (and edr/dbt logs) are gitignored — regenerate locally, or see the
screenshot in the project README.
