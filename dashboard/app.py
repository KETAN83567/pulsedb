"""PulseDB — business dashboard for open-source developer activity.

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

# ---- styling ----
st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; padding-bottom: 2rem; }
      div[data-testid="stMetric"] {
          background: linear-gradient(180deg, #161b29 0%, #11151f 100%);
          border: 1px solid #232a3d; border-radius: 14px; padding: 14px 16px;
      }
      div[data-testid="stMetricValue"] { font-size: 1.7rem; }
      div[data-testid="stMetricLabel"] { color: #9aa4bf; }
      .hero h1 { margin-bottom: 0; font-size: 2.1rem;
          background: linear-gradient(90deg,#a78bfa,#22d3ee);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      .hero p { color: #9aa4bf; margin-top: 4px; }
      .stTabs [data-baseweb="tab"] { font-size: 1.0rem; padding: 10px 18px; }
    </style>
    """,
    unsafe_allow_html=True,
)

CAT = alt.Scale(scheme="tableau20")

m = data.headline_metrics()
fr = data.freshness()

st.markdown(
    f"""
    <div class="hero">
      <h1>📊 PulseDB — Open-Source Developer Activity</h1>
      <p>Repository momentum, contribution mix, and contributor analytics from GitHub Archive ·
         {int(fr.get('batches', 0))} ingested batch(es) · last load {fr.get('last_loaded_at')}</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# ---- KPI row ----
k = st.columns(6)
k[0].metric("Events", f"{int(m['events']):,}")
k[1].metric("Repositories", f"{int(m['repos']):,}")
k[2].metric("Actors", f"{int(m['actors']):,}")
k[3].metric("Avg events / repo", f"{m['avg_events_per_repo']:.1f}")
k[4].metric("Bot share", f"{m['bot_share_pct']:.1f}%", help="Share of events from [bot] accounts")
k[5].metric("Quarantined", f"{int(m['quarantined']):,}", help=f"{m['quarantine_rate_pct']:.2f}% of bronze")

st.divider()

tab_activity, tab_repos, tab_people = st.tabs(["📈 Activity", "📦 Repositories", "👥 Contributors"])

# ============================ ACTIVITY ============================
with tab_activity:
    st.subheader("Event volume over time")
    st.caption("Drag horizontally across the top timeline to recompute the event-type breakdown below for that window.")
    pmt = data.per_minute_by_type()

    brush = alt.selection_interval(encodings=["x"])
    timeline = (
        alt.Chart(pmt)
        .mark_area(line={"color": "#8b5cf6"}, color=alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="#0b0e14", offset=0), alt.GradientStop(color="#8b5cf6", offset=1)],
            x1=1, x2=1, y1=1, y2=0))
        .encode(
            x=alt.X("minute:T", title=None),
            y=alt.Y("sum(events):Q", title="Events / min"),
            tooltip=[alt.Tooltip("minute:T"), alt.Tooltip("sum(events):Q", title="events")],
        )
        .add_params(brush)
        .properties(height=160, width="container")
    )
    breakdown = (
        alt.Chart(pmt)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("sum(events):Q", title="Events in window"),
            y=alt.Y("event_type:N", sort="-x", title=None),
            color=alt.Color("event_type:N", scale=CAT, legend=None),
            tooltip=["event_type:N", alt.Tooltip("sum(events):Q", title="events")],
        )
        .transform_filter(brush)
        .properties(height=380, width="container")
    )
    st.altair_chart(alt.vconcat(timeline, breakdown, spacing=12), width="stretch")

    st.write("")
    c1, c2 = st.columns([2, 3])
    with c1:
        st.subheader("Event mix")
        mix = data.event_type_mix()
        donut = (
            alt.Chart(mix)
            .mark_arc(innerRadius=62)
            .encode(
                theta="events:Q",
                color=alt.Color("event_type:N", scale=CAT, legend=alt.Legend(title="Type")),
                tooltip=["event_type:N", "events:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(donut, width="stretch")
    with c2:
        st.subheader("Composition over time")
        area = (
            alt.Chart(pmt)
            .mark_area()
            .encode(
                x=alt.X("minute:T", title=None),
                y=alt.Y("events:Q", stack="normalize", title="Share"),
                color=alt.Color("event_type:N", scale=CAT, legend=None),
                tooltip=["minute:T", "event_type:N", "events:Q"],
            )
            .properties(height=320)
        )
        st.altair_chart(area, width="stretch")

    st.write("")
    st.subheader("Event-type intensity heatmap")
    st.caption("Where activity concentrates: each cell is one event type in one minute.")
    heat = (
        alt.Chart(pmt)
        .mark_rect()
        .encode(
            x=alt.X("minute:T", title=None),
            y=alt.Y("event_type:N", title=None),
            color=alt.Color("events:Q", scale=alt.Scale(scheme="magma"),
                            legend=alt.Legend(title="Events / min")),
            tooltip=["minute:T", "event_type:N", "events:Q"],
        )
        .properties(height=380)
    )
    st.altair_chart(heat, width="stretch")

# ============================ REPOSITORIES ============================
with tab_repos:
    top = st.columns([3, 2])
    with top[0]:
        st.subheader("Repository momentum")
        min_actors = st.slider(
            "Minimum distinct actors (filters out single-actor bot/automation repos)",
            1, 10, 2,
            help="Raw momentum over-rewards single-actor automation. Require ≥2 actors for a credible signal.",
        )
        lb = data.momentum_leaderboard(min_actors=min_actors, limit=15)
        if lb.empty:
            st.info("No repos match this filter.")
        else:
            bars = (
                alt.Chart(lb)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("momentum_score:Q", title="Momentum score"),
                    y=alt.Y("repo_name:N", sort="-x", title=None),
                    color=alt.Color("active_actors:Q", scale=alt.Scale(scheme="viridis"),
                                    legend=alt.Legend(title="Actors")),
                    tooltip=["repo_name", "momentum_score", "total_events", "active_actors",
                             "push_events", "pr_events", "review_events"],
                )
                .properties(height=440)
            )
            st.altair_chart(bars, width="stretch")
    with top[1]:
        st.subheader("Events per repo")
        st.caption("The long tail: most repos see a handful of events; a few are very active.")
        dist = data.repo_event_distribution()
        hist = (
            alt.Chart(dist)
            .mark_bar(cornerRadiusEnd=4, color="#22d3ee")
            .encode(
                x=alt.X("bucket:N", sort=alt.SortField("ord"), title="Events per repo"),
                y=alt.Y("repos:Q", title="Repositories", scale=alt.Scale(type="log")),
                tooltip=["bucket:N", "repos:Q"],
            )
            .properties(height=440)
        )
        st.altair_chart(hist, width="stretch")

    st.divider()
    st.subheader("🔎 Repository drill-down")
    repo = st.selectbox("Pick a repository (top 300 by activity; type to search)", data.repo_options())
    if repo:
        detail = data.repo_detail(repo)
        s = detail["summary"]
        if s:
            d = st.columns(3)
            d[0].metric("Events", f"{int(s['total_events']):,}")
            d[1].metric("Distinct actors", f"{int(s['distinct_actors']):,}")
            d[2].metric("Active window", f"{s['first_seen_at']:%H:%M} → {s['last_seen_at']:%H:%M}")
        dc = st.columns([2, 3])
        with dc[0]:
            bt = detail["by_type"]
            st.altair_chart(
                alt.Chart(bt).mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("events:Q", title="Events"),
                    y=alt.Y("event_type:N", sort="-x", title=None),
                    color=alt.Color("event_type:N", scale=CAT, legend=None),
                    tooltip=["event_type", "events"],
                ).properties(height=300, title="By event type"),
                width="stretch",
            )
        with dc[1]:
            tl = detail["timeline"]
            st.altair_chart(
                alt.Chart(tl).mark_area(
                    line={"color": "#22d3ee"}, color="#22d3ee44"
                ).encode(
                    x=alt.X("minute:T", title=None),
                    y=alt.Y("events:Q", title="Events / min"),
                    tooltip=["minute:T", "events:Q"],
                ).properties(height=300, title="Activity timeline"),
                width="stretch",
            )
        st.dataframe(
            detail["top_actors"], hide_index=True, width="stretch",
            column_config={
                "actor_login": "Top contributor",
                "events": st.column_config.ProgressColumn(
                    "Events", format="%d",
                    max_value=int(detail["top_actors"]["events"].max()) if not detail["top_actors"].empty else 1),
            },
        )

# ============================ CONTRIBUTORS ============================
with tab_people:
    split = data.contributor_split()
    sc = st.columns(4)
    human = split[split["kind"] == "Human"]
    bot = split[split["kind"] == "Bot"]
    h_ev = int(human["events"].sum()) if not human.empty else 0
    b_ev = int(bot["events"].sum()) if not bot.empty else 0
    h_ac = int(human["actors"].sum()) if not human.empty else 0
    b_ac = int(bot["actors"].sum()) if not bot.empty else 0
    sc[0].metric("Human actors", f"{h_ac:,}")
    sc[1].metric("Bot actors", f"{b_ac:,}")
    sc[2].metric("Human events", f"{h_ev:,}")
    sc[3].metric("Bot events", f"{b_ev:,}")

    st.divider()
    cc = st.columns([3, 2])
    with cc[0]:
        st.subheader("Top contributors")
        exclude_bots = st.checkbox("Exclude bots ([bot] accounts)", value=True)
        contrib = data.top_contributors(exclude_bots=exclude_bots, limit=15)
        st.altair_chart(
            alt.Chart(contrib).mark_bar(cornerRadiusEnd=4, color="#a78bfa").encode(
                x=alt.X("total_events:Q", title="Events"),
                y=alt.Y("actor_login:N", sort="-x", title=None),
                tooltip=["actor_login", "total_events", "distinct_repos"],
            ).properties(height=440),
            width="stretch",
        )
    with cc[1]:
        st.subheader("Human vs bot")
        st.altair_chart(
            alt.Chart(split).mark_arc(innerRadius=55).encode(
                theta="events:Q",
                color=alt.Color("kind:N", scale=alt.Scale(range=["#f59e0b", "#8b5cf6"]),
                                legend=alt.Legend(title=None)),
                tooltip=["kind", "events", "actors"],
            ).properties(height=300),
            width="stretch",
        )
        st.dataframe(
            contrib, hide_index=True, width="stretch",
            column_config={
                "actor_login": "Actor",
                "total_events": st.column_config.ProgressColumn(
                    "Events", format="%d",
                    max_value=int(contrib["total_events"].max()) if not contrib.empty else 1),
                "distinct_repos": st.column_config.NumberColumn("Repos", format="%d"),
            },
        )
