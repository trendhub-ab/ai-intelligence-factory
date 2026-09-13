#!/usr/bin/env python3
"""Fail closed when executable member-sync safety drifts.

Protect current machine-verifiable member contracts only. Historical Run labels,
canonical-spec wording, reference prose, and past measurements are not CI invariants.
"""
from __future__ import annotations

from pathlib import Path

from member_presentation_identity import (
    ALLOW_CREATE_DEFAULT,
    API_HOST_PAGE_ID,
    CANONICAL_DATABASE_ID,
    CANONICAL_DATA_SOURCE_ID,
)

ROOT = Path(__file__).resolve().parent
BODY = "member_ux_body_fast.py"
CHECKPOINT = "member_body_delta_checkpoint.py"
WORKFLOW = ".github/workflows/member-presentation-sync.yml"
SUBSCRIBER_WORKFLOW = ".github/workflows/subscriber-decision-brief.yml"


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _missing(text: str, markers: tuple[str, ...], prefix: str) -> list[str]:
    return [f"{prefix}_missing:{marker}" for marker in markers if marker not in text]


def _workflow_run_block(text: str) -> str:
    if "workflow_run:" not in text:
        return ""
    tail = text.split("workflow_run:", 1)[1]
    return tail.split("types: [completed]", 1)[0]


def collect_errors(root: Path = ROOT) -> list[str]:
    body = _read(root, BODY)
    checkpoint = _read(root, CHECKPOINT)
    workflow = _read(root, WORKFLOW)
    subscriber_workflow = _read(root, SUBSCRIBER_WORKFLOW)
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

    # Destination identity is an operational safety invariant, not documentation history.
    errors += _missing(
        workflow,
        (
            "Resolve canonical member DB",
            f"MEMBER_PRESENTATION_CANONICAL_DATABASE_ID: '{CANONICAL_DATABASE_ID}'",
            f"MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID: '{CANONICAL_DATA_SOURCE_ID}'",
            f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{API_HOST_PAGE_ID}'",
            f"MEMBER_PRESENTATION_ALLOW_CREATE: '{ALLOW_CREATE_DEFAULT}'",
        ),
        "member_destination",
    )

    # Member-derived Notion writes must serialize, and these deterministic transforms
    # must not silently acquire a model dependency.
    errors += _missing(
        workflow,
        (
            "group: member-derived-notion-writes",
            "cancel-in-progress: false",
            "Subscriber Decision Brief Sync",
        ),
        "member_execution",
    )
    if "GEMINI_API_KEY" in workflow:
        errors.append("member_execution_forbidden:GEMINI_API_KEY")

    # Inventory plan is read-only. Only successful main apply runs may fan out into
    # subscriber/member writes, and Member Presentation must follow the brief writer
    # rather than race Daily or Inventory directly.
    errors += _missing(
        subscriber_workflow,
        (
            "Subscriber Inventory Bootstrap",
            "workflow_dispatch:",
            "github.event.workflow_run.name == 'Subscriber Inventory Bootstrap'",
            "contains(github.event.workflow_run.display_title, '[apply]')",
            "group: member-derived-notion-writes",
            "cancel-in-progress: false",
        ),
        "subscriber_execution",
    )
    subscriber_block = _workflow_run_block(subscriber_workflow)
    for forbidden in (
        "Daily Intelligence & Content Pipeline [ONE-SHOT]",
        "Daily Intelligence & Content Pipeline [PAUSED]",
    ):
        if forbidden in subscriber_block:
            errors.append(f"subscriber_execution_forbidden:{forbidden}")
    if "GEMINI_API_KEY" in subscriber_workflow:
        errors.append("subscriber_execution_forbidden:GEMINI_API_KEY")

    presentation_block = _workflow_run_block(workflow)
    for forbidden in (
        "Daily Intelligence & Content Pipeline",
        "Subscriber Inventory Bootstrap",
    ):
        if forbidden in presentation_block:
            errors.append(f"member_execution_forbidden_direct_trigger:{forbidden}")

    return list(dict.fromkeys(errors))


def main() -> int:
    errors = collect_errors(ROOT)
    if errors:
        print("MEMBER_SYNC_SAFETY_GUARD=FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("MEMBER_SYNC_SAFETY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
