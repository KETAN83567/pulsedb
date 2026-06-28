-- Grain contract for agg_daily_repo_momentum: at most one row per (repo, day).
-- A singular test passes when it returns ZERO rows.
select
    repo_id,
    event_date,
    count(*) as n
from {{ ref('agg_daily_repo_momentum') }}
group by repo_id, event_date
having count(*) > 1
