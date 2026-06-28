-- Gold dimension: one row per actor (GitHub user/bot).
with events as (
    select * from {{ ref('stg_events') }}
)

select
    md5(cast(actor_id as varchar)) as actor_sk, -- surrogate key
    actor_id,
    max(actor_login) as actor_login, -- latest-seen login
    min(created_at_utc) as first_seen_at,
    max(created_at_utc) as last_seen_at,
    count(*) as total_events,
    count(distinct repo_id) as distinct_repos
from events
group by actor_id
