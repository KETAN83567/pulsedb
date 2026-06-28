# ADR-0002: Schematize at ingest (lightweight bronze)

**Status:** Accepted (2026-06-28)

## Context

GH Archive events carry large nested payloads (commit lists, PR/issue bodies,
review diffs). The first ingestion stored the full raw JSON per event. One hour
(~267k events) ballooned the DuckDB file to **~2.2 GB** and the load timed out.

## Decision

Project each event at ingest time to the columns PulseDB actually uses:
`event_id, event_type, actor_id, actor_login, repo_id, repo_name, created_at,
payload_action`, plus lineage columns `_source_file` and `_loaded_at`. Drop the
heavy payload bodies.

## Consequences

- Same hour now occupies **~29 MB** (~75× smaller); load is fast and memory-flat
  (streaming decompression, line by line).
- No loss of analytical value for momentum/activity metrics. `payload_action`
  preserves the one nested field that matters (opened/closed/started).
- **Trade-off:** analyses needing raw payload bodies would require re-ingest with
  a wider projection. Acceptable — bronze is cheap to rebuild from the immutable
  GH Archive source.
- This is a deliberate "schema-on-write at bronze" choice for a local warehouse;
  a cloud object-store lake might keep raw payloads in cheap storage instead.
