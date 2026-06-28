-- Silver: clean, typed events that pass the data-quality contract.
-- Incremental: each dlt load stamps a batch with one _loaded_at; the watermark
-- below grabs only strictly-newer batches. delete+insert on event_id keeps
-- re-runs idempotent (no duplicates).
{{
    config(
        materialized="incremental",
        unique_key="event_id",
        incremental_strategy="delete+insert",
    )
}}

select
    event_id,
    event_type,
    actor_id,
    actor_login,
    repo_id,
    repo_name,
    created_at_utc,
    event_date,
    payload_action,
    _source_file,
    _loaded_at
from {{ ref('base_gh_events') }}
where dq_reason is null
{% if is_incremental() %}
    and _loaded_at > (
        select coalesce(max(_loaded_at), '1900-01-01 00:00:00+00'::timestamptz)
        from {{ this }}
    )
{% endif %}
