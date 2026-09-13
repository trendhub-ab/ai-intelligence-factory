"""Run409/411: approved-lane retry ownership plus precise Fact repair guidance.

Run409 fixes a retry-owner ordering bug: after one ordinary HARD quality retry, safe
Reader-only blockers can still claim Run360's already-existing dedicated Reader Repair.

Run411 is installed from the same approved-only overlay boundary. Real approved Run #15
showed that the single HARD quality retry could leave valid Fact blockers
``unsupported vague quantified claim`` and ``LIMITATION_DROPPED``. Run411 does not relax
those blockers or add a model call; it only makes their patch instruction explicit.

Neither layer raises any API budget, relaxes any Gate, or changes normal
Daily/article_validation/pending_retry/X behavior.
"""
from __future__ import annotations

from typing import Any

import run208_reader_value_repair as canonical_reader
import run411_fact_retry_specificity

_INSTALLED_ATTR = "_run409_approved_reader_owner_bridge_installed"
APPROVED_ORIGIN = "approved_article_apply"
MASKED_REASON = "run360_base_quality_retry_already_spent"
READER_REPAIR_REASON = "run409_approved_canonical_reader_repair"


def _eligible(pipeline_module: Any, rows: list[dict], evidence_result: dict | None) -> bool:
    if not canonical_reader._fresh_evidence_safe(pipeline_module, evidence_result):
        return False
    hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
    return canonical_reader._reader_only_repairable(
        rows,
        canonical_reader._FRESH_REPAIRABLE,
        hard,
    )


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    # Run411 shares this exact owner-approved boundary but changes only the existing
    # quality-retry instruction. Install it before wrapping retry ownership.
    run411_fact_retry_specificity.install(pipeline_module)

    original = getattr(pipeline_module, "should_attempt_dynamic_retry", None)
    if not callable(original):
        raise RuntimeError("Run409 requires canonical retry policy")

    def should_attempt_dynamic_retry_with_reader_owner_bridge(
        reason_rows: list[dict],
        evidence_result: dict | None,
        candidate_origin: str = "new",
    ):
        allowed, reason = original(reason_rows, evidence_result, candidate_origin)
        origin = str(candidate_origin or "new").strip()
        if allowed or origin != APPROVED_ORIGIN or reason != MASKED_REASON:
            return allowed, reason

        rows = list(reason_rows or [])
        if not _eligible(pipeline_module, rows, evidence_result):
            return allowed, reason

        if bool(getattr(pipeline_module, canonical_reader._READER_REPAIR_SPENT_ATTR, False)):
            return False, "run360_reader_repair_already_spent"

        # Claim the existing canonical Reader Repair owner. This is not a new retry
        # category: it uses Run360's already-defined dedicated Reader Repair slot.
        setattr(pipeline_module, canonical_reader._READER_REPAIR_SPENT_ATTR, True)
        return True, READER_REPAIR_REASON

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_reader_owner_bridge
    pipeline_module.RUN409_APPROVED_READER_OWNER_BRIDGE = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
