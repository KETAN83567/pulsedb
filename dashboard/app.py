"""PulseDB dashboard — business view (open-source developer activity).

Run:  uv run streamlit run dashboard/app.py
The pipeline-health page lives in dashboard/pages/ and appears in the sidebar.
"""

import sys
from pathlib import Path

# Ensure the project root is importable no matter how Streamlit sets sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import data  # noqa: E402

st.set_page_config(page_title="PulseDB — Developer Activity", page_icon="📊", layout="wide")

st.title("📊 PulseDB — Open-Source Developer Activity")
st.caption("Repo momentum, contribution mix, and top contributors from GitHub Archive events.")

# --- headline metrics ---
m = data.headline_metrics()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Events", f"{int(m['events']):,}")
c2.metric("Repositories", f"{int(m['repos']):,}")
c3.metric("Actors", f"{int(m['actors']):,}")
c4.metric("Quarantined", f"{int(m['quarantined']):,}", help="Rows that failed the data-quality contract")

st.divider()

# --- momentum leaderboard ---
left, right = st.columns([3, 2])
with left:
    st.subheader("Repository momentum")
    min_actors = st.slider(
        "Minimum distinct actors (filter out single-actor bot/automation repos)",
        min_value=1, max_value=10, value=2,
        help="Raw momentum over-rewards single-actor automation pushing thousands of events. "
             "Require ≥2 distinct actors for a more meaningful signal.",
    )
    lb = data.momentum_leaderboard(min_actors=min_actors, limit=15)
    if lb.empty:
        st.info("No repos match this filter.")
    else:
        chart = (
            alt.Chart(lb)
            .mark_bar()
            .encode(
                x=alt.X("momentum_score:Q", title="Momentum score"),
                y=alt.Y("repo_name:N", sort="-x", title=None),
                tooltip=["repo_name", "momentum_score", "total_events", "active_actors"],
            )
            .properties(height=420)
        )
        st.altair_chart(chart, width="stretch")

with right:
    st.subheader("Event type mix")
    mix = data.event_type_mix()
    donut = (
        alt.Chart(mix)
        .mark_arc(innerRadius=60)
        .encode(
            theta=alt.Theta("events:Q"),
            color=alt.Color("event_type:N", title="Event type"),
            tooltip=["event_type", "events"],
        )
        .properties(height=420)
    )
    st.altair_chart(donut, width="stretch")

st.divider()

# --- top contributors ---
st.subheader("Top contributors")
exclude_bots = st.checkbox("Exclude bots ([bot] accounts)", value=True)
contrib = data.top_contributors(exclude_bots=exclude_bots, limit=15)
st.dataframe(
    contrib,
    width="stretch",
    hide_index=True,
    column_config={
        "actor_login": "Actor",
        "total_events": st.column_config.NumberColumn("Events", format="%d"),
        "distinct_repos": st.column_config.NumberColumn("Repos touched", format="%d"),
    },
)
