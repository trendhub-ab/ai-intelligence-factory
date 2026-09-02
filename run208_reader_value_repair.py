"""Run208: bounded Reader Value repair for Pending Retry fast lane only.

Business goal: recover otherwise publishable manuscripts that already passed factual,
evidence, and publication checks but were held for reader-value issues such as a dense
report rhythm or repetitive insight. This layer never relaxes a gate. It only permits
one existing dynamic-recompose call when the narrow fast-lane context proves that the
only blockers are repairable Reader Value review reasons.
"""
from __future__ import annotations

import os
from typing import Any

FAST_LANE_ENV = "AIIF_PENDING_RETRY_FAST_LANE"
_INSTALLED_ATTR = "_run208_reader_value_repair_installed"
_SPENT_ATTR = "_run208_reader_value_repair_spent"
READER_VALUE_MARKER = "reader_value_review:"
_REPAIRABLE = ("dense_report_cluster", "repetitive_insight")


def _message(row: dict) -> str:
    return str(row.get("message") or row.get("reason") or "")


def _reader_only_repairable(rows: list[dict]) -> bool:
    if not rows:
        return False
    for row in rows:
        message = _message(row)
        if READER_VALUE_MARKER not in message:
            return False
        if not any(label in message for label in _REPAIRABLE):
            return False
    return True


def install(pipeline_module: Any) -> Any:
    """Permit at most one Reader Value dynamic repair in the dedicated fast lane."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original = pipeline_module.should_attempt_dynamic_retry
    setattr(pipeline_module, _SPENT_ATTR, False)

    def should_attempt_dynamic_retry_with_reader_repair(
        reason_rows: list[dict], evidence_result: dict | None, candidate_origin: str = "new"
    ):
        allowed, reason = original(reason_rows, evidence_result, candidate_origin)
        if allowed:
            return allowed, reason

        if os.getenv(FAST_LANE_ENV, "") != "1":
            return allowed, reason
        if candidate_origin != "pending_retry":
            return allowed, reason
        if evidence_result is None:
            return allowed, reason
        if getattr(pipeline_module, _SPENT_ATTR, False):
            return allowed, reason
        if reason != "reader_value_review_no_retry":
            return allowed, reason
        rows = list(reason_rows or [])
        if not _reader_only_repairable(rows):
            return allowed, reason

        # One process-local repair maximum. Existing provider, per-run and Pending
        # Retry budgets remain authoritative, so this cannot create an unbounded loop.
        setattr(pipeline_module, _SPENT_ATTR, True)
        return True, "run208_reader_value_fast_lane_repair"

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_reader_repair
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
