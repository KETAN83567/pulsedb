# ADR-0003: Quarantine bad rows instead of dropping them

**Status:** Accepted (2026-06-28)

## Context

Some events may violate the data-quality contract (missing `event_id`,
`event_type`, `repo_id`, `actor_id`, or `created_at`). Silently filtering them
out hides data loss and makes "the numbers look fine" while they aren't.

## Decision

- A shared ephemeral model, `base_gh_events`, types every bronze row and computes
  a `dq_reason` (NULL = passes the contract).
- `stg_events` selects rows where `dq_reason is null`; `quarantine_events`
  selects rows where `dq_reason is not null`, keeping the reason for audit.
- A singular test, `assert_bronze_reconciliation.sql`, enforces the invariant
  **`raw_count == stg_count + quarantine_count`** — every bronze row is either
  cleaned or quarantined, never lost.

## Consequences

- Data loss becomes impossible to hide: the reconciliation test fails loudly if
  any row goes missing.
- Bad data stays inspectable (with a reason) instead of vanishing.
- The contract lives in exactly one place (`base_gh_events`), so Silver and
  quarantine can never drift apart.
