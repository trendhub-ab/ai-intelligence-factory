#!/usr/bin/env python3
"""Fail closed if Run271 member-body delta sync is partially reverted."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _require(path: str, markers: tuple[str, ...]) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise SystemExit(f"Run271 contract missing in {path}: {missing}")


def main() -> int:
    _require(
        "member_ux_body_fast.py",
        (
            "MEMBER_BODY_CHANGED_SINCE",
            "MEMBER_BODY_FORCE_FULL",
            "def _select_delta_pages",
            "def _sentinel_requires_full",
            '"full_contract_mismatch"',
            '"scanned_body_pages"',
            '"skipped_by_delta"',
        ),
    )
    _require(
        "member_body_delta_checkpoint.py",
        (
            "select_previous_successful_start",
            "fetch_previous_successful_start",
            '"fallback_if_missing": "full_scan"',
            "run_started_at",
            "conclusion",
            'head_branch") or "") != "main"',
        ),
    )
    _require(
        ".github/workflows/member-presentation-sync.yml",
        (
            "force_full_body_sync",
            "actions: read",
            "Resolve previous successful member sync checkpoint",
            "member_body_delta_checkpoint.py",
            "MEMBER_BODY_CHANGED_SINCE",
            "MEMBER_BODY_FORCE_FULL",
            "github.run_attempt > 1",
            "tests/test_run271_member_body_delta_sync.py",
            "tests/test_run271_1_member_body_checkpoint.py",
        ),
    )
    _require(
        ".github/workflows/repository-falsification.yml",
        (
            "python run271_member_body_delta_sync_guard.py",
            "python -m unittest tests.test_run271_1_member_body_checkpoint -v",
        ),
    )
    _require(
        "AI_Intelligence_Factory_最終仕様書.md",
        (
            "Run271 — Member Body Delta Sync",
            "MEMBER_BODY_CHANGED_SINCE",
            "前回成功",
            "sentinel",
        ),
    )
    _require(
        "docs/reference/RUN271_MEMBER_BODY_DELTA_SYNC.md",
        (
            "Run271 — Member Body Delta Sync",
            "last_edited_time",
            "previous successful",
            "sentinel",
            "Run271 does not claim a production timing improvement",
        ),
    )
    print("Run271 member body delta sync guard: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
