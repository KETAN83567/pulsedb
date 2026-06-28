-- Silver: events that FAILED the data-quality contract. Kept (not dropped) so
-- every bronze row is accounted for and bad data is auditable, not invisible.
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
