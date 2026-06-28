-- Silver: events that FAILED the data-quality contract. Kept (not dropped) so
-- every bronze row is accounted for and bad data is auditable, not invisible.
-- Incremental on the same _loaded_at watermark as stg_events.
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
    repo_id,
    created_at_tz,
    payload_action,
    dq_reason,
    _source_file,
    _loaded_at
from {{ ref('base_gh_events') }}
where dq_reason is not null
{% if is_incremental() %}
    -- coalesce: quarantine can be empty, and max() of an empty table is NULL.
    and _loaded_at > (
        select coalesce(max(_loaded_at), '1900-01-01 00:00:00+00'::timestamptz)
        from {{ this }}
    )
{% endif %}
