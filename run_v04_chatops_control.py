#!/usr/bin/env python3
"""Owner-only ChatOps authorization for bounded v0.4 note inspect/recovery.

The retired V1 ChatOps workflows remain disabled. This is an independent,
exactly scoped bridge to the existing v04-single-note-draft-bridge.yml.
No data from the private source Issue enters this event authorization.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPOSITORY = "trendhub-ab/ai-intelligence-factory"
CONTROL_ISSUE = 71
CONTROL_TITLE = "AIIF ChatOps Control"
OWNER = "trendhub-ab"
COMMAND = "/aiif v04 inspect 204"
RECOVERY_COMMAND = "/aiif v04 recover 204"


def authorize_event(
    event: dict[str, Any], *, repository: str, event_name: str,
    ref: str, actor: str, run_attempt: str,
) -> dict[str, Any]:
    """Reject all but the owner-authored exact control-Issue comment."""
    denied = {"authorized": False, "reason": "not_authorized"}
    if (
        type(event) is not dict
        or repository != REPOSITORY
        or event_name != "issue_comment"
        or ref != "refs/heads/main"
        or actor != OWNER
        or run_attempt != "1"
        or event.get("action") != "created"
    ):
        return denied
    repo = event.get("repository")
    issue = event.get("issue")
    comment = event.get("comment")
    sender = event.get("sender")
    if not all(type(value) is dict for value in (repo, issue, comment, sender)):
        return denied
    if (
        repo.get("full_name") != REPOSITORY
        or type(issue.get("number")) is not int
        or issue["number"] != CONTROL_ISSUE
        or issue.get("title") != CONTROL_TITLE
        or issue.get("state") != "open"
        or "pull_request" in issue
        or (issue.get("user") or {}).get("login") != OWNER
        or (comment.get("user") or {}).get("login") != OWNER
        or sender.get("login") != OWNER
        or comment.get("author_association") != "OWNER"
        or comment.get("body") not in (COMMAND, RECOVERY_COMMAND)
        or type(comment.get("id")) is not int
        or comment["id"] <= 0
    ):
        return denied
    operation = "recover" if comment["body"] == RECOVERY_COMMAND else "inspect"
    return {"authorized": True, "operation": operation, "comment_id": comment["id"]}


def main() -> int:
    path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        raise SystemExit("V04_CHATOPS_EVENT_MISSING")
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    result = authorize_event(
        event, repository=os.environ.get("GITHUB_REPOSITORY", ""),
        event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
        ref=os.environ.get("GITHUB_REF", ""),
        actor=os.environ.get("GITHUB_ACTOR", ""),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    )
    if not result["authorized"]:
        raise SystemExit("V04_CHATOPS_UNAUTHORIZED")
    output = os.environ.get("GITHUB_OUTPUT", "")
    if not output:
        raise SystemExit("V04_CHATOPS_OUTPUT_MISSING")
    with Path(output).open("a", encoding="utf-8") as writer:
        writer.write("authorized=true\n")
        writer.write(f"operation={result['operation']}\n")
        writer.write(f"comment_id={result['comment_id']}\n")
    print("V04_CHATOPS_OWNER_OPERATION_AUTHORIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
