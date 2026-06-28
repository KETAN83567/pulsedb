"""Read-only data access for the Streamlit dashboard.

Opens the DuckDB warehouse read-only so the dashboard never contends with the
pipeline's writer. Query results are cached; rerun to refresh.
"""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parents[1] / "pulsedb.duckdb"


def _query(sql: str) -> pd.DataFrame:
    # A fresh read-only connection per query keeps things simple and avoids
    # holding a handle that would block the pipeline's writer.
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()


def _esc(value: str) -> str:
    """Escape a single-quoted SQL literal."""
    return value.replace("'", "''")


# ---------- business metrics ----------


@st.cache_data(ttl=60)
def headline_metrics() -> dict:
    df = _query(
        """
        with f as (select * from main.fact_events)
        select
            (select count(*) from f) as events,
            (select count(*) from main.dim_repo) as repos,
            (select count(*) from main.dim_actor) as actors,
            (select count(*) from main.quarantine_events) as quarantined,
            (select count(distinct event_type) from f) as event_types,
            (select count(*) from f where actor_id in
                (select actor_id from main.dim_actor where actor_login ilike '%[bot]%')
            ) as bot_events,
            (select max(c) from (
                select count(*) c from f group by date_trunc('minute', created_at_utc)
            )) as peak_minute
        """
    )
    row = df.iloc[0].to_dict()
    row["avg_events_per_repo"] = (row["events"] / row["repos"]) if row["repos"] else 0
    row["bot_share_pct"] = (100.0 * row["bot_events"] / row["events"]) if row["events"] else 0
    total = row["events"] + row["quarantined"]
    row["quarantine_rate_pct"] = (100.0 * row["quarantined"] / total) if total else 0
    return row


@st.cache_data(ttl=60)
def per_minute_by_type() -> pd.DataFrame:
    """Per-minute event counts by type — the spine of the linked timeline."""
    return _query(
        """
        select
            date_trunc('minute', created_at_utc) as minute,
            event_type,
            count(*) as events
        from main.fact_events
        group by 1, 2
        order by 1
        """
    )


@st.cache_data(ttl=60)
def event_type_mix() -> pd.DataFrame:
    return _query(
        """
        select event_type, count(*) as events
        from main.fact_events
        group by event_type
        order by events desc
        """
    )


@st.cache_data(ttl=60)
def momentum_leaderboard(min_actors: int = 1, limit: int = 20) -> pd.DataFrame:
    return _query(
        f"""
        select repo_name, momentum_score, total_events, active_actors,
               push_events, pr_events, issue_events, star_events, fork_events, review_events
        from main.agg_daily_repo_momentum
        where active_actors >= {int(min_actors)}
        order by momentum_score desc
        limit {int(limit)}
        """
    )


@st.cache_data(ttl=60)
def repo_event_distribution() -> pd.DataFrame:
    """Long-tail histogram: how many repos fall in each events-per-repo bucket."""
    return _query(
        """
        with binned as (
            select case
                when total_events = 1 then '1'
                when total_events between 2 and 3 then '2-3'
                when total_events between 4 and 10 then '4-10'
                when total_events between 11 and 50 then '11-50'
                when total_events between 51 and 200 then '51-200'
                else '200+'
            end as bucket,
            case
                when total_events = 1 then 1
                when total_events between 2 and 3 then 2
                when total_events between 4 and 10 then 3
                when total_events between 11 and 50 then 4
                when total_events between 51 and 200 then 5
                else 6
            end as ord
            from main.dim_repo
        )
        select bucket, ord, count(*) as repos
        from binned group by bucket, ord order by ord
        """
    )


@st.cache_data(ttl=60)
def repo_options(limit: int = 300) -> list[str]:
    df = _query(
        f"""
        select repo_name from main.dim_repo
        order by total_events desc limit {int(limit)}
        """
    )
    return df["repo_name"].tolist()


@st.cache_data(ttl=60)
def repo_detail(repo_name: str) -> dict:
    name = _esc(repo_name)
    summary = _query(
        f"""
        select repo_name, total_events, distinct_actors, first_seen_at, last_seen_at
        from main.dim_repo where repo_name = '{name}'
        """
    )
    by_type = _query(
        f"""
        select event_type, count(*) as events
        from main.stg_events where repo_name = '{name}'
        group by 1 order by 2 desc
        """
    )
    timeline = _query(
        f"""
        select date_trunc('minute', created_at_utc) as minute, count(*) as events
        from main.stg_events where repo_name = '{name}'
        group by 1 order by 1
        """
    )
    top_actors = _query(
        f"""
        select actor_login, count(*) as events
        from main.stg_events where repo_name = '{name}'
        group by 1 order by 2 desc limit 10
        """
    )
    return {
        "summary": summary.iloc[0].to_dict() if not summary.empty else {},
        "by_type": by_type,
        "timeline": timeline,
        "top_actors": top_actors,
    }


@st.cache_data(ttl=60)
def top_contributors(exclude_bots: bool = True, limit: int = 20) -> pd.DataFrame:
    bot_filter = "where actor_login not ilike '%[bot]%'" if exclude_bots else ""
    return _query(
        f"""
        select actor_login, total_events, distinct_repos
        from main.dim_actor
        {bot_filter}
        order by total_events desc
        limit {int(limit)}
        """
    )


@st.cache_data(ttl=60)
def contributor_split() -> pd.DataFrame:
    """Human vs bot share of events and actors."""
    return _query(
        """
        select
            case when actor_login ilike '%[bot]%' then 'Bot' else 'Human' end as kind,
            count(*) as actors,
            sum(total_events) as events
        from main.dim_actor
        group by 1
        """
    )


# ---------- pipeline health (reads orchestration's run-metadata) ----------


@st.cache_data(ttl=30)
def has_run_metadata() -> bool:
    df = _query(
        """
        select count(*) as n
        from information_schema.tables
        where table_schema = 'meta' and table_name = 'pipeline_runs'
        """
    )
    return bool(df.iloc[0]["n"])


@st.cache_data(ttl=30)
def pipeline_runs(limit: int = 100) -> pd.DataFrame:
    return _query(
        f"""
        select recorded_at, asset, partition, status, rows, duration_s, error
        from meta.pipeline_runs
        order by recorded_at desc
        limit {int(limit)}
        """
    )


@st.cache_data(ttl=30)
def freshness() -> dict:
    df = _query(
        """
        select
            max(_loaded_at) as last_loaded_at,
            date_diff('hour', max(_loaded_at), now()) as hours_since_load,
            count(distinct _source_file) as batches
        from raw.gh_events
        """
    )
    return df.iloc[0].to_dict()
