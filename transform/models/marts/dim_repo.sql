-- Gold dimension: one row per repository.
with events as (
    select * from {{ ref('stg_events') }}
)

select
    md5(cast(repo_id as varchar)) as repo_sk, -- surrogate key
    repo_id,
    max(repo_name) as repo_name, -- latest-seen name (repos can be renamed)
    min(created_at_utc) as first_seen_at,
    max(created_at_utc) as last_seen_at,
    count(*) as total_events,
    count(distinct actor_id) as distinct_actors
from events
group by repo_id
