# Dashboard (Streamlit)

Two pages, both reading the DuckDB warehouse **read-only** (no contention with
the pipeline writer).

- **Business view** (`app.py`) — headline metrics, repository momentum
  leaderboard, event-type mix, and top contributors.
  - The momentum leaderboard has a **min-distinct-actors filter** (default 2):
    raw momentum over-rewards single-actor automation/bots pushing thousands of
    events, so requiring ≥2 actors surfaces genuinely active projects.
  - Top contributors can exclude `[bot]` accounts.
- **Pipeline Health** (`pages/1_Pipeline_Health.py`) — source freshness vs. SLA,
  run history from `meta.pipeline_runs`, rows ingested per partition, run
  durations, and failures. The operational view most portfolio dashboards omit.

## Run

```bash
uv run streamlit run dashboard/app.py
# opens http://localhost:8501
```

Data comes from the Gold marts and `meta.pipeline_runs`. If the health page is
empty, run the pipeline via Dagster first (see `orchestration/README.md`).
