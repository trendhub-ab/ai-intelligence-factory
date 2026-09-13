"""Run400: let the approved one-article apply lane reuse canonical Reader Repair.

Run208/360 already owns the safe repair policy: evidence must be sufficient and
scope-safe, reader-only blockers are repairable, and at most one dedicated Reader
Repair is allowed after normal re-gating. Run399 introduced a new candidate origin,
``approved_article_apply``, but that origin was not part of Run208's fresh-equivalent
allowlist, so the existing retry owner returned ``reader_value_review_no_retry`` even
when one Deep Dive request remained.

This overlay is deliberately narrow. It does not create a new retry policy or relax a
gate. For the Run399 origin only, it asks the already-installed Run208/360 policy the
same question using the validated ``article_revalidation`` semantics. Every other
origin is passed through unchanged.
"""
from __future__ import annotations

from typing import Any

_INSTALLED_ATTR = "_run400_approved_reader_repair_installed"
APPROVED_ORIGIN = "approved_article_apply"
CANONICAL_EQUIVALENT_ORIGIN = "article_revalidation"


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "should_attempt_dynamic_retry", None)
    if not callable(original):
        raise RuntimeError("Run400 requires canonical should_attempt_dynamic_retry")

    def should_attempt_dynamic_retry_with_approved_apply(
        reason_rows: list[dict],
        evidence_result: dict | None,
        candidate_origin: str = "new",
    ):
        origin = str(candidate_origin or "new").strip()
        if origin == APPROVED_ORIGIN:
            return original(reason_rows, evidence_result, CANONICAL_EQUIVALENT_ORIGIN)
        return original(reason_rows, evidence_result, candidate_origin)

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_approved_apply
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
