#!/usr/bin/env python3
"""Fail closed when member-body delta sync safety drifts.

Protect the executable delta/full-fallback contract only. Historical Run labels,
canonical-spec wording, reference prose, and past performance measurements are not CI invariants.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
BODY = "member_ux_body_fast.py"
CHECKPOINT = "member_body_delta_checkpoint.py"
WORKFLOW = ".github/workflows/member-presentation-sync.yml"


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _missing(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def collect_errors(root: Path = ROOT) -> list[str]:
    body = _read(root, BODY)
    checkpoint = _read(root, CHECKPOINT)
    workflow = _read(root, WORKFLOW)
    errors: list[str] = []

    errors += _missing(
        body,
        (
            "MEMBER_BODY_CHANGED_SINCE",
            "MEMBER_BODY_FORCE_FULL",
            "def _select_delta_pages",
            "def _sentinel_requires_full",
            '"full_contract_mismatch"',
            '"scanned_body_pages"',
            '"skipped_by_delta"',
        ),
        "member_body",
    )
    errors += _missing(
        checkpoint,
        (
            "select_previous_successful_start",
            "fetch_previous_successful_start",
            '"fallback_if_missing": "full_scan"',
            "run_started_at",
            "conclusion",
            'head_branch") or "") != "main"',
        ),
        "checkpoint",
    )
    errors += _missing(
        workflow,
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
        "member_workflow",
    )

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("MEMBER_BODY_DELTA_SYNC_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMBER_BODY_DELTA_SYNC_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
