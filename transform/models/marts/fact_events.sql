-- Gold fact: one row per event, with surrogate FKs to the dimensions.
select
    e.event_id, -- degenerate dimension (natural event key)
    md5(cast(e.repo_id as varchar)) as repo_sk,
    md5(cast(e.actor_id as varchar)) as actor_sk,
    e.repo_id,
    e.actor_id,
    e.event_type,
    e.payload_action,
    e.created_at_utc,
    e.event_date
from {{ ref('stg_events') }} as e
