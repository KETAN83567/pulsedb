# ADR-0001: Incremental event-grain models, full-refresh aggregates

**Status:** Accepted (2026-06-28)

## Context

PulseDB ingests GH Archive hour by hour. Reprocessing all of history on every
run is wasteful and doesn't scale. dbt supports incremental models, but naive
incrementality on aggregates produces wrong results.

## Decision

- **Event-grain models are incremental.** `stg_events`, `quarantine_events`, and
  `fact_events` use `materialized='incremental'` with `incremental_strategy='delete+insert'`
  and `unique_key='event_id'`. On incremental runs they filter
  `_loaded_at > (select coalesce(max(_loaded_at), '1900-01-01+00') from {{ this }})`.
  - Each dlt load stamps a whole batch with one `_loaded_at`, so a strict `>`
    watermark picks up exactly the new batches.
  - `delete+insert` on `event_id` makes re-runs idempotent.
  - `coalesce` floor lets an empty table (e.g. an empty quarantine) still ingest.
- **Aggregates and dimensions are full-refresh** (`dim_repo`, `dim_actor`,
  `int_repo_daily_activity`, `agg_daily_repo_momentum`). They recompute from the
  incremental base each run, because appending to a `GROUP BY` would double-count.

## Consequences

- Reprocessing cost is bounded by *new* data, not total history.
- Aggregates stay correct without complex merge logic; recomputation is cheap
  because the base is already materialized.
- The watermark is the single source of incremental truth — documented in the
  model SQL and tested via the reconciliation invariant.
