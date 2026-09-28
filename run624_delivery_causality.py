#!/usr/bin/env python3
"""Bind ONE-SHOT downstream draft creation to the Ready produced by this run.

The normal note reconciliation may safely inspect all current Ready inventory. Draft creation
is different: a successful Daily with zero new Ready must never fall through to an older queued
article, and a Daily with one or more new Ready articles must pin the child workflow to one of
those exact current-run candidates.

This module reads only the current run's Deep Dive gate-history artifact. It performs no model,
browser, Notion, or note mutation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _safe_default(reason: str) -> dict[str, Any]:
    return {
        "audit_valid": False,
        "ready_count": 0,
        "create_private_draft": False,
        "run_note_reconciliation": True,
        "target_source_url": "",
        "reason": str(reason or "").strip(),
    }


def _http_url(value: Any) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return text


def delivery_decision(gate_history_path: str | Path) -> dict[str, Any]:
    """Return a fail-closed draft decision from one current-run gate-history file."""
    path = Path(gate_history_path)
    if not path.is_file():
        return _safe_default("current-run gate history is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _safe_default("current-run gate history is unreadable")

    if not isinstance(payload, dict):
        return _safe_default("current-run gate history is not an object")
    candidates = payload.get("candidates")
    funnel = payload.get("funnel")
    if not isinstance(candidates, list) or not isinstance(funnel, dict):
        return _safe_default("current-run gate history lacks candidates/funnel")

    ready_rows: list[tuple[int, str]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        if str(row.get("final_status") or "").strip() != "Ready":
            continue
        if row.get("article_saved") is not True:
            continue
        source_url = _http_url(row.get("url"))
        if not source_url:
            return _safe_default("current-run Ready candidate has no valid source URL")
        try:
            rank = int(row.get("candidate_rank"))
        except (TypeError, ValueError):
            return _safe_default("current-run Ready candidate has invalid candidate_rank")
        ready_rows.append((rank, source_url))

    observed_ready = len(ready_rows)
    declared_ready = funnel.get("ready_count")
    if type(declared_ready) is not int or declared_ready < 0:
        return _safe_default("current-run funnel ready_count is invalid")
    if declared_ready != observed_ready:
        return _safe_default(
            f"current-run Ready accounting mismatch: funnel={declared_ready} candidates={observed_ready}"
        )

    ready_rows.sort(key=lambda row: (row[0], row[1]))
    target_source_url = ready_rows[0][1] if ready_rows else ""
    return {
        "audit_valid": True,
        "ready_count": observed_ready,
        "create_private_draft": bool(ready_rows),
        "run_note_reconciliation": True,
        "target_source_url": target_source_url,
        "reason": "current-run Ready pinned" if ready_rows else "current run produced no Ready article",
    }


def _latest_gate_history(directory: str | Path) -> Path | None:
    root = Path(directory)
    if not root.is_dir():
        return None
    rows: list[tuple[str, Path]] = []
    for path in root.glob("*_deep_dive_gate_history_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        generated_at = str((payload or {}).get("generated_at") or "")
        rows.append((generated_at, path))
    if not rows:
        return None
    rows.sort(key=lambda row: (row[0], row[1].name))
    return rows[-1][1]


def decision_from_directory(directory: str | Path) -> dict[str, Any]:
    path = _latest_gate_history(directory)
    if path is None:
        return _safe_default("no Deep Dive gate-history artifact exists for fan-out")
    result = delivery_decision(path)
    result["gate_history_path"] = str(path)
    return result


def _write_github_output(path: str, result: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(f"audit_valid={'true' if result.get('audit_valid') else 'false'}\n")
        fh.write(f"ready_count={int(result.get('ready_count') or 0)}\n")
        fh.write(f"create_private_draft={'true' if result.get('create_private_draft') else 'false'}\n")
        fh.write(f"target_source_url={str(result.get('target_source_url') or '').strip()}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate-history-dir", default="gate_history")
    parser.add_argument("--github-output", default="")
    args = parser.parse_args()
    result = decision_from_directory(args.gate_history_dir)
    _write_github_output(args.github_output, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
