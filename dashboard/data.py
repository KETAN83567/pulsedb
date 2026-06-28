"""Read-only data access for the Streamlit dashboard.

Opens the DuckDB warehouse read-only so the dashboard never contends with the
pipeline's writer. Query results are cached for 60s; rerun to refresh.
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


@st.cache_data(ttl=60)
def headline_metrics() -> dict:
    df = _query(
        """
        select
            (select count(*) from main.fact_events) as events,
            (select count(*) from main.dim_repo) as repos,
            (select count(*) from main.dim_actor) as actors,
            (select count(*) from main.quarantine_events) as quarantined
        """
    )
    return df.iloc[0].to_dict()


@st.cache_data(ttl=60)
def momentum_leaderboard(min_actors: int = 1, limit: int = 20) -> pd.DataFrame:
    return _query(
        f"""
        select repo_name, momentum_score, total_events, active_actors,
               push_events, pr_events, issue_events, star_events
        from main.agg_daily_repo_momentum
        where active_actors >= {int(min_actors)}
        order by momentum_score desc
        limit {int(limit)}
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


# ---- pipeline health (reads orchestration's run-metadata) ----


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
def pipeline_runs(limit: int = 50) -> pd.DataFrame:
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
            date_diff('hour', max(_loaded_at), now()) as hours_since_load
        from raw.gh_events
        """
    )
    return df.iloc[0].to_dict()
