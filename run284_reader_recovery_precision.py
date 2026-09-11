"""Run284: Production findings from bounded current-policy Ready recovery.

Two real recovery attempts established two independent issues:
1. ``_JAPANESE_SAFE_FIXES`` contained an over-broad ``をな... -> を...`` substitution that
   corrupted valid Japanese such as ``迷子をなくす`` into ``迷子をくす``.
2. A candidate with sufficient Evidence and PASS Fact/Editorial/Publication gates could fail
   only Reader Value, yet the dedicated recovery lane spent one generation request and then
   stopped even though its hard budget intentionally allows up to four requests.

This overlay is deliberately narrow:
- disable only the proven unsafe Japanese substitution; all other deterministic fixes remain;
- permit at most one model-based Reader Value repair only for
  ``candidate_origin=current_policy_ready_recovery``;
- require evidence state SUFFICIENT, decision scope safe, reader-only REVIEW reasons, and only
  repairable density/accessibility failures observed in Production;
- preserve the original retry decision everywhere else.

Run352 is chained at the end of this already-canonical post-reader precision installation point.
It does not authorize another retry. It only strengthens the prompt of an already-authorized
retry to preserve non-target reader structure, and repairs the exact stranded adverbial particle
created by deterministic hype deletion. This keeps Production installation order unchanged while
avoiding another orchestration branch in ``production_pipeline.py``.

It adds no provider call by itself. It only authorizes the existing bounded quality-retry path
inside the explicit Run282 recovery workflow, whose four-request hard cap remains authoritative.
"""
from __future__ import annotations

from typing import Any

import run352_retry_preservation

_INSTALL_FLAG = "_run284_reader_recovery_precision_installed"
_SPENT_FLAG = "_run284_current_policy_reader_repair_spent"
READER_VALUE_MARKER = "reader_value_review:"
_DANGEROUS_POLISH_PATTERN = r"をな(?=[一-龥ぁ-んァ-ヶA-Za-z])"

_REPAIRABLE_READER_LABELS = (
    "dense_report_cluster",
    "repetitive_insight",
    "multi_axis_reader_weakness",
    "non_engineer_access_failure",
    "final_surface_multi_axis_reader_weakness",
    "final_surface_non_engineer_access_failure",
)


def disable_overbroad_japanese_polish(pipeline_module: Any) -> int:
    """Remove only the Production-proven unsafe ``をな`` substitution.

    The historical cleanup tuple remains otherwise byte-for-byte equivalent. Returning the
    removal count makes tests fail loudly if a future refactor changes this contract.
    """
    fixes = tuple(getattr(pipeline_module, "_JAPANESE_SAFE_FIXES", ()) or ())
    filtered = tuple(
        (pattern, replacement)
        for pattern, replacement in fixes
        if str(getattr(pattern, "pattern", "")) != _DANGEROUS_POLISH_PATTERN
    )
    pipeline_module._JAPANESE_SAFE_FIXES = filtered
    return len(fixes) - len(filtered)


def _message(row: dict) -> str:
    return str((row or {}).get("message") or (row or {}).get("reason") or "")


def _reader_only_repairable(rows: list[dict], hard_severity: str) -> bool:
    """Accept only the narrow Production-observed Reader Value family."""
    if not rows:
        return False
    saw_repairable = False
    for row in rows:
        if str((row or {}).get("severity") or "") == hard_severity:
            return False
        message = _message(row)
        if READER_VALUE_MARKER not in message:
            return False
        if not any(label in message for label in _REPAIRABLE_READER_LABELS):
            return False
        saw_repairable = True
    return saw_repairable


def _evidence_is_safe_for_reader_repair(pipeline_module: Any, evidence_result: dict | None) -> bool:
    if not isinstance(evidence_result, dict):
        return False
    sufficient = str(getattr(pipeline_module, "EVIDENCE_SUFFICIENT", "SUFFICIENT"))
    if str(evidence_result.get("state") or "") != sufficient:
        return False
    return evidence_result.get("decision_scope_safe") is True


def install(pipeline_module: Any) -> Any:
    """Install after the historical reader bridge / Run208 stack, idempotently."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        # Run352 has its own idempotency marker. Calling it here also makes an older
        # process that pre-installed Run284 but not Run352 converge safely.
        run352_retry_preservation.install(pipeline_module)
        return pipeline_module

    # This removes a deterministic corruption source before any Production generation call.
    disable_overbroad_japanese_polish(pipeline_module)

    original_retry_policy = pipeline_module.should_attempt_dynamic_retry
    setattr(pipeline_module, _SPENT_FLAG, False)

    def should_attempt_dynamic_retry_with_current_policy_reader_repair(
        reason_rows: list[dict],
        evidence_result: dict | None,
        candidate_origin: str = "new",
    ) -> tuple[bool, str]:
        allowed, reason = original_retry_policy(reason_rows, evidence_result, candidate_origin)
        if allowed:
            return allowed, reason
        if candidate_origin != "current_policy_ready_recovery":
            return allowed, reason
        if reason != "reader_value_review_no_retry":
            return allowed, reason
        if bool(getattr(pipeline_module, _SPENT_FLAG, False)):
            return allowed, reason
        if not _evidence_is_safe_for_reader_repair(pipeline_module, evidence_result):
            return allowed, reason
        hard = str(getattr(pipeline_module, "GATE_SEVERITY_HARD", "HARD"))
        rows = list(reason_rows or [])
        if not _reader_only_repairable(rows, hard):
            return allowed, reason

        # One process-local spend maximum. Run282's DEEP_DIVE_MODEL_BUDGET and workflow hard
        # cap remain the real provider quota authority, so this cannot form an unbounded loop.
        setattr(pipeline_module, _SPENT_FLAG, True)
        return True, "run284_current_policy_reader_repair"

    pipeline_module.should_attempt_dynamic_retry = should_attempt_dynamic_retry_with_current_policy_reader_repair

    # Run352 is global retry/rescue precision but intentionally adds no new authorization path.
    # Chaining it here preserves the established post-reader install location in Production.
    run352_retry_preservation.install(pipeline_module)

    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
