"""Run409: unmask canonical dedicated Reader Repair after base quality retry.

Real approved Run399 #11 showed a retry-owner ordering bug. After one ordinary HARD
quality retry, all remaining blockers were Reader-only and Evidence/Publication were
safe. Run208/360 nevertheless returned ``run360_base_quality_retry_already_spent``
before its dedicated Reader Repair branch could claim the manuscript. One approved
request slot remained unused.

This overlay is deliberately narrow:
- only ``approved_article_apply``;
- only when the wrapped policy returns ``run360_base_quality_retry_already_spent``;
- only when every remaining blocker is canonical repairable Reader-only, non-HARD;
- only with Evidence SUFFICIENT and decision_scope_safe=true;
- at most one canonical dedicated Reader Repair.

It does not create another generic quality retry, raise any API budget, relax any Gate,
or change normal Daily/article_validation/pending_retry behavior.
"""
from __future__ import annotations

from typing import Any

import run208_reader_value_repair as canonical_reader

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
