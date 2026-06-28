"""Pipeline-health page — reads orchestration's run-metadata + source freshness.

This is the operational view most portfolio dashboards lack: did the pipeline
run, how fresh is the data, how long did it take, did anything fail.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import data  # noqa: E402

st.set_page_config(page_title="PulseDB — Pipeline Health", page_icon="🩺", layout="wide")

st.title("🩺 Pipeline Health")
st.caption("Operational observability: freshness, run history, throughput, and failures.")

# --- freshness ---
fr = data.freshness()
hours = fr.get("hours_since_load")
c1, c2 = st.columns(2)
c1.metric("Last load (UTC)", str(fr.get("last_loaded_at")))
if hours is None:
    c2.metric("Freshness", "—")
else:
    status = "🟢 Fresh" if hours < 24 else ("🟡 Stale" if hours < 48 else "🔴 Breached")
    c2.metric("Hours since last load", f"{int(hours)}", help="SLA: warn 24h / error 48h")
    st.write(f"**Freshness SLA:** {status}")

st.divider()

if not data.has_run_metadata():
    st.info(
        "No run metadata yet. Run the pipeline via Dagster to populate "
        "`meta.pipeline_runs` (see orchestration/README.md)."
    )
    st.stop()

runs = data.pipeline_runs(limit=100)

# --- run summary ---
total = len(runs)
failures = int((runs["status"] == "failure").sum())
successes = total - failures
c1, c2, c3 = st.columns(3)
c1.metric("Recorded runs", total)
c2.metric("Successes", successes)
c3.metric("Failures", failures, delta=None if failures == 0 else f"{failures} ⚠️")

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Rows ingested per run")
    ingest = runs[(runs["asset"] == "raw.gh_events") & runs["rows"].notna()]
    if ingest.empty:
        st.info("No ingestion runs recorded yet.")
    else:
        chart = (
            alt.Chart(ingest)
            .mark_bar()
            .encode(
                x=alt.X("partition:N", title="Partition (hour)", sort=None),
                y=alt.Y("rows:Q", title="Rows"),
                tooltip=["partition", "rows", "duration_s"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, width="stretch")

with right:
    st.subheader("Run duration by asset")
    dur = runs[runs["duration_s"].notna()]
    chart = (
        alt.Chart(dur)
        .mark_circle(size=90, opacity=0.7)
        .encode(
            x=alt.X("recorded_at:T", title="Time"),
            y=alt.Y("duration_s:Q", title="Duration (s)"),
            color=alt.Color("asset:N", title="Asset"),
            tooltip=["asset", "partition", "duration_s", "status"],
        )
        .properties(height=320)
    )
    st.altair_chart(chart, width="stretch")

st.divider()
st.subheader("Recent runs")
st.dataframe(
    runs,
    width="stretch",
    hide_index=True,
    column_config={
        "recorded_at": st.column_config.DatetimeColumn("When (UTC)"),
        "duration_s": st.column_config.NumberColumn("Duration (s)", format="%.1f"),
        "rows": st.column_config.NumberColumn("Rows", format="%d"),
    },
)
