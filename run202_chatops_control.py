#!/usr/bin/env python3
"""Fail-closed authorization for the AIIF ChatOps ONE-SHOT bridge.

The normal ChatGPT chat can post an exact command to one dedicated GitHub Issue.
This module never runs Production itself. It only validates the GitHub event and
returns the one allowed ONE-SHOT mode to the workflow, which then dispatches the
existing daily-one-shot.yml with RUN_ONCE on main.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

CONTROL_ISSUE_NUMBER = 71
ALLOWED_LOGIN = "trendhub-ab"
COMMAND_TO_MODE = {
    "/aiif run article_validation": "article_validation",
    "/aiif run full": "full",
}


def authorize_event(event: dict[str, Any]) -> dict[str, Any]:
    issue = event.get("issue") if isinstance(event, dict) else None
    comment = event.get("comment") if isinstance(event, dict) else None
    if not isinstance(issue, dict) or not isinstance(comment, dict):
        return {"authorized": False, "mode": "", "reason": "missing_issue_or_comment"}

    try:
        issue_number = int(issue.get("number"))
    except (TypeError, ValueError):
        return {"authorized": False, "mode": "", "reason": "invalid_issue_number"}
    if issue_number != CONTROL_ISSUE_NUMBER:
        return {"authorized": False, "mode": "", "reason": "wrong_control_issue"}

    if issue.get("pull_request") is not None:
        return {"authorized": False, "mode": "", "reason": "pull_request_comments_forbidden"}

    user = comment.get("user") or {}
    if not isinstance(user, dict) or str(user.get("login") or "") != ALLOWED_LOGIN:
        return {"authorized": False, "mode": "", "reason": "unauthorized_actor"}

    body = comment.get("body")
    if not isinstance(body, str):
        return {"authorized": False, "mode": "", "reason": "invalid_comment_body"}
    mode = COMMAND_TO_MODE.get(body)
    if not mode:
        return {"authorized": False, "mode": "", "reason": "command_not_allowed"}

    return {"authorized": True, "mode": mode, "reason": "authorized"}


def _write_github_output(result: dict[str, Any]) -> None:
    output_path = str(os.environ.get("GITHUB_OUTPUT") or "").strip()
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as fh:
        fh.write(f"authorized={'true' if result.get('authorized') else 'false'}\n")
        fh.write(f"mode={str(result.get('mode') or '')}\n")
        fh.write(f"reason={str(result.get('reason') or '')}\n")


def main() -> int:
    event_path = str(os.environ.get("GITHUB_EVENT_PATH") or "").strip()
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is required")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    result = authorize_event(event)
    _write_github_output(result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
