"""Run406/407: one extra Reader-only repair for the exact owner-approved apply lane.

Normal Production keeps Run360's bounded ownership: one ordinary quality retry plus
one dedicated Reader Repair. The Run399 lane is uniquely constrained by an explicit
owner approval token, one exact article target, and a dedicated request budget of five.
Run406 authorized the extra repair when only ``multi_axis_reader_weakness`` remained.

Real production Run #7 falsified that condition as too narrow: after the first Reader
Repair, the same safe manuscript retained the reader-only bundle
``dense_report_cluster`` + ``multi_axis_reader_weakness`` +
``non_engineer_access_failure``. Publication Readiness still passed, Evidence remained
safe, and the fifth request was unused. Run407 therefore accepts that exact class of
reader-only residuals as well as the original multi-axis-only residual.

It never raises API budgets, never relaxes a gate, never admits HARD/non-reader rows,
and never permits a third Reader repair. Full gates rerun after the model call;
provider/request-budget layers remain fail-closed.
"""
from __future__ import annotations

from typing import Any

import run208_reader_value_repair as canonical_reader

_INSTALLED_ATTR = "_run406_approved_second_reader_repair_installed"
_SECOND_SPENT_ATTR = "_run406_approved_second_reader_repair_spent"
APPROVED_ORIGIN = "approved_article_apply"
SECOND_REPAIR_REASON = "run406_approved_second_reader_repair"
_ALLOWED_RESIDUALS = frozenset({
    "dense_report_cluster",
    "multi_axis_reader_weakness",
    "non_engineer_access_failure",
})


def _residual_labels(rows: list[dict]) -> set[str]:
    labels: set[str] = set()
    for row in rows or []:
        message = canonical_reader._message(row)
        matched = {label for label in _ALLOWED_RESIDUALS if label in message}
        if not matched:
            return set()
        labels.update(matched)
    return labels


def _eligible_residual(pipeline_module: Any, rows: list[dict], evidence_result: dict | None) -> bool:
    if not canonical_reader._fresh_evidence_safe(pipeline_module, evidence_result):
        return False
    hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
    if not canonical_reader._reader_only_repairable(rows, canonical_reader._FRESH_REPAIRABLE, hard):
        return False
    labels = _residual_labels(rows)
    if not labels or "multi_axis_reader_weakness" not in labels:
        return False
    # Run407 is deliberately narrow: every residual must be one of the three reader-density
    # findings reproduced by the real approved RubyGems run. Fact/score/final-surface or any
    # unknown Reader finding stays fail-closed.
    return labels.issubset(_ALLOWED_RESIDUALS)


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module

    original = getattr(pipeline_module, "should_attempt_dynamic_retry", None)
    if not callable(original):
        raise RuntimeError("Run406 requires canonical retry policy")

    setattr(pipeline_module, _SECOND_SPENT_ATTR, False)

    def should_attempt_dynamic_retry_with_approved_second_reader_repair(
        reason_rows: list[dict],
        evidence_result: dict | None,
        candidate_origin: str = "new",
    ):
        allowed, reason = original(reason_rows, evidence_result, candidate_origin)
        origin = str(candidate_origin or "new").strip()
        if allowed or origin != APPROVED_ORIGIN:
            return allowed, reason
        if reason != "run360_reader_repair_already_spent":
            return allowed, reason
        if bool(getattr(pipeline_module, _SECOND_SPENT_ATTR, False)):
            return False, "run406_second_reader_repair_already_spent"
        rows = list(reason_rows or [])
        if not _eligible_residual(pipeline_module, rows, evidence_result):
            return allowed, reason
        setattr(pipeline_module, _SECOND_SPENT_ATTR, True)
        return True, SECOND_REPAIR_REASON

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_approved_second_reader_repair
    pipeline_module.RUN406_APPROVED_SECOND_READER_REPAIR = True
    pipeline_module.RUN407_OBSERVED_READER_RESIDUAL_BUNDLE = True
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
