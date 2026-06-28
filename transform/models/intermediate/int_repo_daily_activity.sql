-- Intermediate: per repo, per UTC day, pivot event counts into activity columns.
-- This is the reusable building block the gold momentum aggregate sits on.
with events as (
    select * from {{ ref('stg_events') }}
)

select
    repo_id,
    max(repo_name) as repo_name, -- repo_name can change; take the latest-seen label for the day
    event_date,
    count(*) as total_events,
    count(distinct actor_id) as active_actors,
    count(*) filter (where event_type = 'PushEvent') as push_events,
    count(*) filter (where event_type = 'PullRequestEvent') as pr_events,
    count(*) filter (where event_type = 'IssuesEvent') as issue_events,
    count(*) filter (where event_type = 'WatchEvent') as star_events,
    count(*) filter (where event_type = 'ForkEvent') as fork_events,
    count(*) filter (where event_type = 'PullRequestReviewEvent') as review_events
from events
group by repo_id, event_date
