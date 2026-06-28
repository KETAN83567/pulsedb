"""Failure alerting: open a GitHub issue when a Dagster run fails.

Activates only when GITHUB_TOKEN and GITHUB_REPOSITORY (e.g. "owner/repo") are
set in the environment; otherwise it degrades to a logged warning so the
pipeline runs identically with or without credentials. The token is read from
env at runtime and never logged or committed.
"""

import os

import requests
from dagster import RunFailureSensorContext, run_failure_sensor


def _open_github_issue(title: str, body: str) -> str:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
    if not token or not repo:
        return "skipped (GITHUB_TOKEN / GITHUB_REPOSITORY not set) — logged only"

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": body, "labels": ["pipeline-failure"]},
        timeout=30,
    )
    resp.raise_for_status()
    return f"opened issue #{resp.json().get('number')}"


@run_failure_sensor(description="Open a GitHub issue when a pipeline run fails.")
def github_issue_on_failure(context: RunFailureSensorContext) -> None:
    run = context.dagster_run
    title = f"[PulseDB] Pipeline run failed: {run.job_name}"
    body = (
        f"**Job:** {run.job_name}\n"
        f"**Run ID:** {run.run_id}\n"
        f"**Error:**\n```\n{context.failure_event.message}\n```\n"
    )
    outcome = _open_github_issue(title, body)
    context.log.warning(f"Run {run.run_id} failed → GitHub alert: {outcome}")
