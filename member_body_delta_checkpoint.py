#!/usr/bin/env python3
"""Resolve the last successful Member Presentation Sync start time.

The delta body sync must catch not only property changes made by the current
presentation phase, but also manual/generated-body edits that happened after the
previous successful member sync. The previous successful run start time is a
safe overlap checkpoint: edits made during that prior run are rechecked once on
the next run instead of being silently skipped.

If GitHub Actions history cannot be read, emit no cutoff. The body sync then
falls back to its legacy full scan, preserving correctness over speed.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

WORKFLOW_FILE = "member-presentation-sync.yml"
API_ROOT = "https://api.github.com"


def select_previous_successful_start(
    payload: dict[str, Any], *, current_run_id: int | None = None
) -> str:
    """Return newest successful main-run start time from a GitHub runs payload."""
    candidates: list[tuple[str, int, str]] = []
    for run in payload.get("workflow_runs") or []:
        if not isinstance(run, dict):
            continue
        try:
            run_id = int(run.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if current_run_id and run_id == current_run_id:
            continue
        if str(run.get("conclusion") or "") != "success":
            continue
        if str(run.get("head_branch") or "") != "main":
            continue
        started = str(run.get("run_started_at") or "").strip()
        created = str(run.get("created_at") or started).strip()
        if not started:
            continue
        candidates.append((created, run_id, started))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def fetch_previous_successful_start(
    *, repository: str, token: str, current_run_id: int | None = None
) -> str:
    if not repository or not token:
        return ""
    workflow = quote(WORKFLOW_FILE, safe="")
    url = (
        f"{API_ROOT}/repos/{repository}/actions/workflows/{workflow}/runs"
        "?branch=main&status=completed&per_page=20"
    )
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-intelligence-factory-member-body-checkpoint",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return ""
    return select_previous_successful_start(payload, current_run_id=current_run_id)


def _append_github_env(name: str, value: str) -> None:
    path = str(os.environ.get("GITHUB_ENV") or "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def main() -> int:
    repository = str(os.environ.get("GITHUB_REPOSITORY") or "").strip()
    token = str(os.environ.get("GITHUB_TOKEN") or "").strip()
    raw_run_id = str(os.environ.get("GITHUB_RUN_ID") or "").strip()
    try:
        current_run_id = int(raw_run_id) if raw_run_id else None
    except ValueError:
        current_run_id = None

    cutoff = fetch_previous_successful_start(
        repository=repository,
        token=token,
        current_run_id=current_run_id,
    )
    _append_github_env("MEMBER_BODY_CHANGED_SINCE", cutoff)
    print(
        json.dumps(
            {
                "checkpoint_found": bool(cutoff),
                "cutoff": cutoff,
                "fallback_if_missing": "full_scan",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
