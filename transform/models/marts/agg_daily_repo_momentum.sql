-- Gold aggregate: the headline metric. A weighted daily "momentum" score per
-- repo, plus day-over-day change. Weights reflect contribution signal strength
-- (a merged-PR-grade event counts more than a star). Tune in one place here.
with daily as (
    select * from {{ ref('int_repo_daily_activity') }}
),

scored as (
    select
        repo_id,
        repo_name,
        event_date,
        total_events,
        active_actors,
        push_events,
        pr_events,
        issue_events,
        star_events,
        fork_events,
        review_events,
        (
            push_events * 1.0
            + pr_events * 4.0
            + review_events * 3.0
            + issue_events * 2.0
            + fork_events * 2.0
            + star_events * 1.0
        ) as momentum_score
    from daily
)

select
    *,
    -- Day-over-day delta within each repo (NULL on a repo's first observed day).
    momentum_score - lag(momentum_score) over (
        partition by repo_id order by event_date
    ) as momentum_score_dod_change
from scored
