-- Silver: clean, typed events that pass the data-quality contract.
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
