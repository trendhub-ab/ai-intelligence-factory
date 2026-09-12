from types import SimpleNamespace

import run208_reader_value_repair as r208


def _row(message):
    return {"message": "reader_value_review:" + message, "severity": "REVIEW"}


def test_density_failure_gets_deletion_not_more_explanation_instruction():
    text = r208._run359_targeted_repair([_row("non_engineer_access_failure")])
    assert "専門語密度を下げる" in text
    assert "不要な名称を捨てる" in text
    assert "専門語を別の専門語で説明しない" in text
    assert "3個以上" in text


def test_final_summary_jargon_targets_source_sentences_not_gate_relaxation():
    text = r208._run359_targeted_repair([_row("final_surface_summary_jargon_cluster")])
    assert "30秒要約の素材を平易化する" in text
    assert "本文から自動抽出" in text
    assert "Factを削るのではなく" in text
    assert "閾値" not in text


def test_unrelated_reader_reason_does_not_invent_targeted_directive():
    assert r208._run359_targeted_repair([_row("title_flattening")]) == ""


def test_install_appends_targeted_contract_without_new_call_site():
    def retry(rows, evidence, origin="new"):
        return False, "reader_value_review_no_retry"

    def prompt(*args, **kwargs):
        return "BASE"

    def retry_instruction(rows):
        return "RETRY", ["reader"]

    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=retry,
        build_decision_prompt=prompt,
        build_dynamic_retry_instruction=retry_instruction,
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    instruction, sections = pipeline.build_dynamic_retry_instruction([
        _row("multi_axis_reader_weakness"),
        _row("final_surface_summary_jargon_cluster"),
    ])
    assert "Reader Repair" in instruction
    assert "RUN359 Reader Repair Execution Contract" in instruction
    assert "専門語密度を下げる" in instruction
    assert "30秒要約の素材を平易化する" in instruction
    assert sections == ["reader"]
    assert pipeline.RUN359_READER_REPAIR_EXECUTION is True


def test_reader_retry_budget_and_evidence_safety_remain_authoritative():
    calls = {"count": 0}

    def retry(rows, evidence, origin="new"):
        calls["count"] += 1
        return False, "reader_value_review_no_retry"

    pipeline = SimpleNamespace(
        should_attempt_dynamic_retry=retry,
        build_decision_prompt=lambda: "BASE",
        build_dynamic_retry_instruction=lambda rows: ("RETRY", []),
        GATE_SEVERITY_HARD="HARD",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
    )
    r208.install(pipeline)
    rows = [_row("non_engineer_access_failure")]
    assert pipeline.should_attempt_dynamic_retry(rows, {"state": "INSUFFICIENT", "decision_scope_safe": False}, "new") == (False, "reader_value_review_no_retry")
    assert pipeline.should_attempt_dynamic_retry(rows, {"state": "SUFFICIENT", "decision_scope_safe": True}, "new") == (True, "run341_production_reader_repair")
    assert calls["count"] == 2
