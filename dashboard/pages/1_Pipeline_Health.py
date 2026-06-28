"""Pipeline-health page — reads orchestration's run-metadata + source freshness.

The operational view most portfolio dashboards lack: did the pipeline run, how
fresh is the data, how much throughput, how long did it take, did anything fail.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import data  # noqa: E402

st.set_page_config(page_title="PulseDB — Pipeline Health", page_icon="🩺", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.2rem; }
      div[data-testid="stMetric"] {
          background: linear-gradient(180deg,#161b29,#11151f);
          border: 1px solid #232a3d; border-radius: 14px; padding: 14px 16px; }
      div[data-testid="stMetricLabel"] { color: #9aa4bf; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🩺 Pipeline Health")
st.caption("Operational observability: freshness SLA, throughput, run durations, and failures.")

fr = data.freshness()
hours = fr.get("hours_since_load")

has_meta = data.has_run_metadata()
runs = data.pipeline_runs(limit=200) if has_meta else None

# ---- status banner ----
if hours is None:
    sla, sla_color = "Unknown", "gray"
elif hours < 24:
    sla, sla_color = "Fresh", "green"
elif hours < 48:
    sla, sla_color = "Stale (warn)", "orange"
else:
    sla, sla_color = "Breached", "red"

failures = int((runs["status"] == "failure").sum()) if has_meta and not runs.empty else 0
if failures == 0 and sla in ("Fresh", "Unknown"):
    st.success(f"🟢 Pipeline healthy — freshness: {sla} · 0 failed runs recorded", icon="✅")
elif failures > 0:
    st.error(f"🔴 {failures} failed run(s) recorded — investigate below", icon="🚨")
else:
    st.warning(f"🟡 Freshness {sla} — pipeline may not have run recently", icon="⚠️")

# ---- KPI row ----
total = len(runs) if has_meta and runs is not None else 0
successes = total - failures
success_rate = (100.0 * successes / total) if total else 0.0
total_rows = int(runs["rows"].fillna(0).sum()) if has_meta and not runs.empty else 0
avg_dur = float(runs["duration_s"].dropna().mean()) if has_meta and not runs.empty and runs["duration_s"].notna().any() else 0.0

k = st.columns(5)
k[0].metric("Freshness SLA", sla, help="warn 24h / error 48h, keyed on _loaded_at")
k[1].metric("Hours since load", "—" if hours is None else f"{int(hours)}")
k[2].metric("Success rate", f"{success_rate:.0f}%", help=f"{successes}/{total} runs")
k[3].metric("Rows ingested", f"{total_rows:,}")
k[4].metric("Avg run", f"{avg_dur:.1f}s")

st.divider()

if not has_meta or runs is None or runs.empty:
    st.info(
        "No run metadata yet. Run the pipeline via Dagster to populate "
        "`meta.pipeline_runs` (see orchestration/README.md)."
    )
    st.stop()

left, right = st.columns([3, 2])
with left:
    st.subheader("Rows ingested per partition")
    ingest = runs[(runs["asset"] == "raw.gh_events") & runs["rows"].notna()]
    if ingest.empty:
        st.info("No ingestion runs recorded yet.")
    else:
        st.altair_chart(
            alt.Chart(ingest).mark_bar(cornerRadiusEnd=4, color="#22d3ee").encode(
                x=alt.X("partition:N", title="Partition (hour)", sort=None),
                y=alt.Y("rows:Q", title="Rows"),
                tooltip=["partition", "rows", "duration_s", "status"],
            ).properties(height=320),
            width="stretch",
        )
with right:
    st.subheader("Run outcomes")
    outcome = runs.groupby("status").size().reset_index(name="runs")
    st.altair_chart(
        alt.Chart(outcome).mark_arc(innerRadius=55).encode(
            theta="runs:Q",
            color=alt.Color("status:N",
                            scale=alt.Scale(domain=["success", "failure"], range=["#22c55e", "#ef4444"]),
                            legend=alt.Legend(title=None)),
            tooltip=["status", "runs"],
        ).properties(height=320),
        width="stretch",
    )

st.subheader("Run duration timeline")
st.altair_chart(
    alt.Chart(runs[runs["duration_s"].notna()]).mark_circle(size=120, opacity=0.8).encode(
        x=alt.X("recorded_at:T", title="Time"),
        y=alt.Y("duration_s:Q", title="Duration (s)"),
        color=alt.Color("asset:N", legend=alt.Legend(title="Asset")),
        size=alt.Size("rows:Q", legend=None),
        tooltip=["asset", "partition", "duration_s", "rows", "status"],
    ).properties(height=260).interactive(),
    width="stretch",
)

st.divider()
st.subheader("Recent runs")
show = runs.copy()
show["status"] = show["status"].map({"success": "✅ success", "failure": "❌ failure"}).fillna(show["status"])
st.dataframe(
    show, hide_index=True, width="stretch",
    column_config={
        "recorded_at": st.column_config.DatetimeColumn("When (UTC)"),
        "asset": "Asset",
        "partition": "Partition",
        "status": "Status",
        "duration_s": st.column_config.NumberColumn("Duration (s)", format="%.1f"),
        "rows": st.column_config.NumberColumn("Rows", format="%d"),
        "error": "Error",
    },
)
