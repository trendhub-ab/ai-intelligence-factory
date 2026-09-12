from types import SimpleNamespace

import run284_reader_recovery_precision as run284


class _Pattern:
    def __init__(self, pattern):
        self.pattern = pattern


def _pipeline():
    def base_retry(reason_rows, evidence_result, candidate_origin="new"):
        return False, "reader_value_review_no_retry"

    return SimpleNamespace(
        _JAPANESE_SAFE_FIXES=((_Pattern(run284._DANGEROUS_POLISH_PATTERN), "safe"),),
        should_attempt_dynamic_retry=base_retry,
        EVIDENCE_SUFFICIENT="SUFFICIENT",
        GATE_SEVERITY_HARD="HARD",
        build_decision_prompt=lambda *args, **kwargs: "prompt",
    )


def _safe_evidence():
    return {"state": "SUFFICIENT", "decision_scope_safe": True}


def _reader_row(label="dense_report_cluster", severity="REVIEW"):
    return {"severity": severity, "message": f"reader_value_review:{label}"}


def test_pending_validation_reader_only_gets_exactly_one_repair():
    p = _pipeline()
    run284.install(p)
    first = p.should_attempt_dynamic_retry([_reader_row()], _safe_evidence(), "pending_retry_validation")
    second = p.should_attempt_dynamic_retry([_reader_row()], _safe_evidence(), "pending_retry_validation")
    assert first == (True, "run284_pending_retry_reader_repair")
    assert second == (False, "reader_value_review_no_retry")


def test_observed_reader_cluster_including_final_summary_jargon_is_repairable():
    p = _pipeline()
    run284.install(p)
    rows = [
        _reader_row("dense_report_cluster"),
        _reader_row("multi_axis_reader_weakness"),
        _reader_row("non_engineer_access_failure"),
        _reader_row("final_surface_summary_jargon_cluster"),
    ]
    assert p.should_attempt_dynamic_retry(rows, _safe_evidence(), "pending_retry_validation") == (
        True,
        "run284_pending_retry_reader_repair",
    )


def test_pending_validation_rejects_hard_reader_blocker():
    p = _pipeline()
    run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row(severity="HARD")], _safe_evidence(), "pending_retry_validation") == (False, "reader_value_review_no_retry")


def test_pending_validation_rejects_mixed_fact_and_reader_blockers():
    p = _pipeline()
    run284.install(p)
    rows = [_reader_row(), {"severity": "HARD", "message": "fact_validation:unsupported_claim"}]
    assert p.should_attempt_dynamic_retry(rows, _safe_evidence(), "pending_retry_validation") == (False, "reader_value_review_no_retry")


def test_pending_validation_rejects_unsafe_evidence():
    p = _pipeline()
    run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row()], {"state": "INSUFFICIENT", "decision_scope_safe": False}, "pending_retry_validation") == (False, "reader_value_review_no_retry")


def test_normal_fresh_origin_remains_ineligible():
    p = _pipeline()
    run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row()], _safe_evidence(), "new") == (False, "reader_value_review_no_retry")


def test_existing_current_policy_lane_remains_authorized():
    p = _pipeline()
    run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row("non_engineer_access_failure")], _safe_evidence(), "current_policy_ready_recovery") == (True, "run284_current_policy_reader_repair")
