-- Gold fact: one row per event, with surrogate FKs to the dimensions.
-- Incremental on the same _loaded_at watermark as the Silver layer.
{{
    config(
        materialized="incremental",
        unique_key="event_id",
        incremental_strategy="delete+insert",
    )
}}

select
    e.event_id, -- degenerate dimension (natural event key)
    md5(cast(e.repo_id as varchar)) as repo_sk,
    md5(cast(e.actor_id as varchar)) as actor_sk,
    e.repo_id,
    e.actor_id,
    e.event_type,
    e.payload_action,
    e.created_at_utc,
    e.event_date,
    e._loaded_at
from {{ ref('stg_events') }} as e
{% if is_incremental() %}
where e._loaded_at > (
    select coalesce(max(_loaded_at), '1900-01-01 00:00:00+00'::timestamptz)
    from {{ this }}
)
{% endif %}
