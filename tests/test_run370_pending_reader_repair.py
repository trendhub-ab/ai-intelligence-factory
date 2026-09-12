from types import SimpleNamespace
import run284_reader_recovery_precision as run284

class _Pattern:
    def __init__(self, pattern): self.pattern = pattern

def _pipeline():
    def base_retry(reason_rows, evidence_result, candidate_origin="new"):
        return False, "reader_value_review_no_retry"
    return SimpleNamespace(_JAPANESE_SAFE_FIXES=((_Pattern(run284._DANGEROUS_POLISH_PATTERN), "safe"),), should_attempt_dynamic_retry=base_retry, EVIDENCE_SUFFICIENT="SUFFICIENT", GATE_SEVERITY_HARD="HARD", build_decision_prompt=lambda *args, **kwargs: kwargs.get("quality_feedback", "prompt"))

def _safe_evidence(): return {"state":"SUFFICIENT","decision_scope_safe":True}
def _reader_row(label="dense_report_cluster", severity="REVIEW"): return {"severity":severity,"message":f"reader_value_review:{label}"}

def test_pending_validation_reader_only_gets_exactly_one_repair():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row()],_safe_evidence(),"pending_retry_validation")== (True,"run284_pending_retry_reader_repair")
    assert p.should_attempt_dynamic_retry([_reader_row()],_safe_evidence(),"pending_retry_validation")== (False,"reader_value_review_no_retry")

def test_observed_reader_cluster_is_repairable():
    p=_pipeline(); run284.install(p)
    rows=[_reader_row("dense_report_cluster"),_reader_row("multi_axis_reader_weakness"),_reader_row("non_engineer_access_failure"),_reader_row("final_surface_summary_jargon_cluster")]
    assert p.should_attempt_dynamic_retry(rows,_safe_evidence(),"pending_retry_validation")== (True,"run284_pending_retry_reader_repair")

def test_pending_validation_rejects_hard_reader_blocker():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row(severity="HARD")],_safe_evidence(),"pending_retry_validation")[0] is False

def test_pending_validation_rejects_mixed_fact_and_reader_blockers():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row(),{"severity":"HARD","message":"fact_validation:unsupported_claim"}],_safe_evidence(),"pending_retry_validation")[0] is False

def test_pending_validation_rejects_unsafe_evidence():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row()],{"state":"INSUFFICIENT","decision_scope_safe":False},"pending_retry_validation")[0] is False

def test_normal_fresh_origin_remains_ineligible():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row()],_safe_evidence(),"new")[0] is False

def test_existing_current_policy_lane_remains_authorized():
    p=_pipeline(); run284.install(p)
    assert p.should_attempt_dynamic_retry([_reader_row("non_engineer_access_failure")],_safe_evidence(),"current_policy_ready_recovery")== (True,"run284_current_policy_reader_repair")

def test_run373_plan_is_reason_specific_and_stable():
    rows=[_reader_row("dense_report_cluster"),_reader_row("multi_axis_reader_weakness"),_reader_row("non_engineer_access_failure")]
    assert run284.deterministic_reader_repair_plan(rows)==("dense_report_cluster","multi_axis_reader_weakness","non_engineer_access_failure")
    text=run284.reader_repair_feedback(rows)
    assert "1段落1論点" in text
    assert "何が変わった→今どう判断する→判断を変える重要制約" in text
    assert "冒頭約600文字" in text

def test_run373_reader_feedback_does_not_add_fact_preservation_order_freeze():
    feedback="【Reader Repair｜Factを固定した読者導線修正】\nreader_value_review:dense_report_cluster\nreader_value_review:non_engineer_access_failure"
    out=run284.retry_feedback_with_preservation(feedback,"previous")
    assert "RUN373 Reason-Specific Reader Repair" in out
    assert "1段落1論点" in out
    assert run284.RETRY_PRESERVATION_CONTRACT not in out

def test_run373_unknown_or_fact_reason_cannot_create_reader_plan():
    rows=[{"severity":"REVIEW","message":"fact_validation:unsupported_claim"},{"severity":"REVIEW","message":"reader_value_review:unknown_future_label"}]
    assert run284.deterministic_reader_repair_plan(rows)==()
    assert run284.reader_repair_feedback(rows)==""
